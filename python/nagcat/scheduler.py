# Copyright 2008-2009 ITA Software, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Core scheduler

The basic object for a class is a Runnable. All classes used for tasks
must be subclasses of Runnable. Runnable's store the tasks' repeat
interval and any subtasks it depends on.

The Scheduler class handles running the Runnables.

Scheduling works as follows:
    1. During startup all top level tasks are added to the scheduler
       via schobj.register()
    2. After all initialization is finished schobj.start() is called.
    3. Before start() starts scheduling stuff it runs _create_groups()
       to group all top level tasks which have any subtasks in common.
       This ensures that tests that need to run the same queries are
       run at the same time.
    4. All top level objects are started in a random interval between
       now and their repeat interval to distribute things.
    5. Each time a top level task finishes it will reschedule itself.
"""

import time
import socket
import random
from collections import deque

from twisted.internet import defer, reactor
from twisted.python import failure
from coil.struct import Struct

from nagcat import errors, util, log

class Scheduler(object):
    """Run things!"""

    def __init__(self):
        self._registered = set()
        self._startup = True
        self._running = False
        self._latency = deque([0], 60)
        self._task_stats = {
                'count': 0,
                'Group': {'count': 0},
                'Test':  {'count': 0},
                'Query': {'count': 0},
            }

    def register(self, runnable):
        """Register a top level Runnable to be run directly by the scheduler"""
        assert self._startup
        assert runnable not in self._registered
        assert isinstance(runnable, Runnable)

        self._registered.add(runnable)
        runnable.scheduler = self

    def unregister(self, runnable):
        """Unregister a top level Runnable"""
        assert runnable in self._registered

        runnable.scheduler = None
        self._registered.remove(runnable)

        if not self._registered:
            self.stop()
            return

    def stats(self):
        """Get a variety of stats to report on"""

        data = {'tasks': self._task_stats}
        data['latency'] = {
                'period':  60, # Approximate but close enough
                'max': max(self._latency),
                'min': min(self._latency),
                'avg': sum(self._latency) / len(self._latency),
            }

        return data

    def _create_groups(self):
        """Group together registered tasks with common subtasks.

        When top level tasks are grouped they are unregistered and
        added as dependencies to a dummy Runnable object that is then
        registered.
        """

        def update_stats(runnable):
            self._task_stats['count'] += 1
            if isinstance(runnable, query.Query):
                self._task_stats['Query']['count'] += 1
                if runnable.name in self._task_stats['Query']:
                    self._task_stats['Query'][runnable.name]['count'] += 1
                else:
                    self._task_stats['Query'][runnable.name] = {'count': 1}
            elif isinstance(runnable, test.Test):
                self._task_stats['Test']['count'] += 1
            elif isinstance(runnable, RunnableGroup):
                self._task_stats['Group']['count'] += 1
            else: # shouldn't happen, but just in case...
                if 'Other' in self._task_stats:
                    self._task_stats['Other']['count'] += 1
                else:
                    self._task_stats['Other'] = {'count': 1}

        groups_by_member = {} # indexed by id()
        groups = set()

        for runnable in self._registered:
            deps = set((runnable,))
            for dep in runnable.getAllDependencies():
                # Only group together if the repeat interval matches.
                if dep.repeat == runnable.repeat:
                    deps.add(dep)

            log.trace("Dependencies for %s: %s", runnable, deps)
            new_group = deps.copy()

            # Merge any groups that share members with new_group
            for dep in deps:
                old_group = groups_by_member.get(id(dep), None)
                if old_group is not None:
                    new_group.update(old_group)
                    groups.discard(old_group)
                else:
                    # This dep hasn't been seen yet so record it
                    update_stats(dep)

            # switch to frozenset to make group hashable
            new_group = frozenset(new_group)
            groups.add(new_group)

            for dep in new_group:
                groups_by_member[id(dep)] = new_group

        log.trace("All groups: %s", groups)

        # Create a meta-runnable that will fire off all registered Runnables
        # that are in the same group at the same time.
        for group in groups:
            # Pull all registered runnables out of the group
            group_registered = self._registered.intersection(group)

            # There better be at least one registered item in the group!
            assert group_registered

            # Unregister these runnables
            for old in group_registered:
                self.unregister(old)

            # Setup the meta-runnable
            group_runnable = RunnableGroup(group_registered)
            update_stats(group_runnable)
            self.register(group_runnable)

    def prepare(self):
        """Finish the startup process.

        This must be after all register() calls and before start()
        """
        assert self._startup and not self._running

        tests = len(self._registered)
        self._create_groups()

        if tests > 1:
            log.info("Tasks: %s", self._task_stats['count'])
            log.info("Groups: %s", self._task_stats['Group']['count'])
            log.info("Tests: %s", self._task_stats['Test']['count'])
            log.info("Queries: %s", self._task_stats['Query']['count'])
            for query_type in self._task_stats['Query']:
                if query_type == "count":
                    continue
                log.info("Query %s: %s", query_type,
                        self._task_stats['Query'][query_type]['count'])
            if 'Other' in self._task_stats:
                log.info("Other: %s", self._task_stats['Other']['count'])

        self._startup = False

    def start(self):
        """Start up the scheduler!"""
        assert not self._startup and not self._running
        self._running = True

        if not self._registered:
            self.stop()
            return

        if len(self._registered) == 1:
            # Only running one test, skip the fancy stuff
            reactor.callLater(0, list(self._registered)[0].start)
            return

        # Collect runnables that query the same host so that we can
        # avoid hitting a host with many queries at once
        host_groups = {}
        for runnable in self._registered:
            if runnable.host in host_groups:
                host_groups[runnable.host].append(runnable)
            else:
                host_groups[runnable.host] = [runnable]

        for host_name, host_group in host_groups.iteritems():
            log.debug("Scheduling host %s", host_name)
            # The first runnable in the group will start between now and
            # the end of the slot time period. Any remaining runnables will
            # start after the number of seconds in the slot. This should
            # evenly distribute queries that are sent to the same host.
            slot = 60.0 / len(host_group)
            assert slot
            delay = random.random() * slot

            for runnable in host_group:
                log.debug("Scheduling %s in %s seconds.", runnable, delay)
                reactor.callLater(delay, runnable.start)
                delay += slot

        # Start latency self-checker
        reactor.callLater(1.0, self.latency, time.time())

        log.info("Startup complete, running...")

    def stop(self):
        """Stop the scheduler"""

        # Don't actually stop if _create_groups hasn't finished
        if not self._running:
            return

        if self._registered:
            log.warn("Stopping while still active!")
        else:
            log.info("Nothing left to do, stopping.")

        reactor.stop()

    def latency(self, last):
        now = time.time()
        reactor.callLater(1.0, self.latency, now)

        latency = now - last - 1.0
        self._latency.append(latency)

        if latency > 5.0:
            log.error("Callback latency: %s" % latency)
        elif latency > 1.5:
            log.warn("Callback latency: %s" % latency)


class Runnable(object):
    """This class is used for starting various processing chunks such
    as tests and queries. Any child of this class will likely want to
    override _start to actually run its task.
    """

    def __init__(self, conf):
        self.__depends = set()
        self.scheduler = None
        self.lastrun = 0
        self.result = None
        self.deferred = None

        assert isinstance(conf, Struct)
        conf.expand(recursive=False)

        self.label = conf.get('label', "")
        self.host = conf.get('host', None)

        try:
            self.repeat = util.Interval(conf.get('repeat', '1m'))
        except util.IntervalError, ex:
            raise errors.ConfigError(conf, "Invalid repeat: %s" % ex)

        if 'addr' in conf:
            self.addr = conf['addr']
        elif self.host:
            try:
                self.addr = socket.gethostbyname(self.host)
            except socket.gaierror, ex:
                raise errors.InitError("Failed to resolve '%s': %s"
                        % (self.host, ex))
        else:
            self.addr = None

    def _start(self):
        """Start a Runnable object, return a Deferred.
        
        Override this method when subclassing.
        Do not call this method directly.
        """
        return defer.succeed(None)

    def __startDependencies(self):
        if self.__depends:
            log.debug("Starting dependencies for %s", self)
            deferlist = []
            for dep in self.__depends:
                deferlist.append(dep.start())
            return defer.DeferredList(deferlist)
        else:
            return defer.succeed(None)

    def __startSelf(self, results):
        log.debug("Starting %s", self)
        return self._start()

    def start(self):
        """Start a Runnable object"""

        # Don't start again if we are already running
        if self.deferred is not None:
            return self.deferred

        # Reuse old results if our time isn't up yet
        if self.lastrun + self.repeat.seconds > time.time():
            log.debug("Skipping start of %s", self)
            if self.scheduler:
                log.warn("Top level task got scheduled too soon! "
                        "Scheduling in %s" % self.repeat)
                reactor.callLater(self.repeat.seconds, self.start)
            deferred = defer.succeed(self.result)
            deferred.addBoth(self.__null)
        else:
            # use deferred instead of self.deferred because
            # __done could have been called already
            self.deferred = deferred = self.__startDependencies()
            deferred.addBoth(self.__startSelf)
            deferred.addBoth(self.__done)

        return deferred

    @errors.callback
    def __done(self, result):
        """Save the result, log unhandled errors"""

        log.debug("Stopping %s", self)
        log.debug("Result: %s", result)
        self.result = result
        self.lastrun = time.time()
        self.deferred = None

        if not self.scheduler or not reactor.running:
            # Don't reschedule if not top-level or during shutdown
            pass
        elif self.repeat:
            log.debug("Scheduling %s in %s.", self, self.repeat)
            reactor.callLater(self.repeat.seconds, self.start)
        else:
            log.debug("Unregistering %s, not scheduled to run again.", self)
            self.scheduler.unregister(self)
            self.scheduler = None

        if isinstance(result, failure.Failure):
            if isinstance(result.value, errors.TestError):
                if result.tb is not None:
                    log.warn("TestError with a traceback in %s:\n%s" %
                            (self, result.getTraceback()))
            else:
                log.error("Unhandled error in %s:\n%s" %
                        (self, result.getTraceback()))

    def __null(self, result):
        """Just a sink for results are replayed"""
        pass

    def addDependency(self, dep):
        """Declare that self depends on another Runnable"""

        assert isinstance(dep, Runnable)
        self.__depends.add(dep)

    def getDependencies(self):
        """Get the current set of dependencies"""
        return self.__depends

    def getAllDependencies(self):
        """Get the current set of dependencies recursively"""

        alldeps = set()
        for dep in self.__depends:
            alldeps.add(dep)
            alldeps.update(dep.getAllDependencies())

        return alldeps


class RunnableGroup(Runnable):
    """This type of Runnable does nothing more than provide a top level
    parent for a bunch of other Runnables that must start at the same time.
    """

    def __init__(self, group):
        # Grab the first non-zero repeat value and count hosts
        hosts = {}
        repeat = None
        for dependency in group:
            if not repeat:
                repeat = dependency.repeat

            if dependency.host in hosts:
                hosts[dependency.host] += 1
            else:
                hosts[dependency.host] = 1

        # Select the most common host in the group for this group's host
        # this is used to distribute queries to a host evenly.
        max_host = None
        max_count = 0
        for host, count in hosts.iteritems():
            if count > max_count:
                max_host = host
                max_count = count

        # Setup this Runnable
        conf = Struct({'repeat': repeat, 'host': max_host, 'addr': None})
        Runnable.__init__(self, conf)
        for dependency in group:
            self.addDependency(dependency)

# import late due to circular imports
import test, query

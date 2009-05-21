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
from random import randint

from twisted.internet import defer, reactor

from nagcat import errors, util, log

class Scheduler(object):
    """Run things!"""

    def __init__(self):
        self._registered = set()
        self._running = False

    def register(self, runnable):
        """Register a top level Runnable to be run directly by the scheduler"""
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

    def _create_groups(self):
        """Group together registered tasks with common subtasks.

        When top level tasks are grouped they are unregistered and
        added as dependencies to a dummy Runnable object that is then
        registered.
        """
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
            self.register(group_runnable)

    def start(self):
        """Start up the scheduler!"""

        self._create_groups()
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
            slot = 60 // len(host_group)
            if slot == 0:
                slot = 1

            delay = randint(0, slot)

            for runnable in host_group:
                log.debug("Scheduling %s in %s seconds.", runnable, delay)
                reactor.callLater(delay, runnable.start)
                delay += slot

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


class Runnable(object):
    """This class is used for starting various processing chunks such
    as tests and queries. Any child of this class will likely want to
    override _start to actually run its task.
    """

    def __init__(self, repeat, host=None):
        self.__depends = set()
        self.scheduler = None
        self.lastrun = 0
        self.result = None
        self.deferred = None
        self.repeat = util.Interval(repeat)
        # Used to distribute load during startup
        self.host = host

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
            return defer.succeed(self.result)

        # use deferred instead of self.deferred because
        # __done could have been called already
        self.deferred = deferred = self.__startDependencies()
        deferred.addBoth(self.__startSelf)
        deferred.addBoth(self.__done)
        return deferred

    @errors.callback
    def __done(self, result):
        log.debug("Stopping %s", self)
        log.debug("Result: %s", result)
        self.result = result
        self.lastrun = time.time()
        self.deferred = None

        if self.scheduler and self.repeat:
            log.debug("Scheduling %s in %s.", self, self.repeat)
            reactor.callLater(self.repeat.seconds, self.start)
        elif self.scheduler and not self.repeat:
            log.debug("Unregistering %s, it is not scheduled to run again.", self)
            self.scheduler.unregister(self)

        return result

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
        Runnable.__init__(self, None)

        hosts = {}

        for dependency in group:
            if not self.repeat:
                self.repeat = dependency.repeat
            self.addDependency(dependency)

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

        self.host = max_host


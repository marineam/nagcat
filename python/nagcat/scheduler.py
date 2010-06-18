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
import random
from collections import deque

from twisted.internet import defer, reactor

try:
    from lxml import etree
except ImportError:
    etree = None

from nagcat import log, monitor_api
from nagcat.runnable import Runnable, RunnableGroup

class SchedulerPage(monitor_api.XMLPage):
    """Information on objects in the Nagcat scheduler"""

    def __init__(self, scheduler):
        super(SchedulerPage, self).__init__()
        self.scheduler = scheduler

    def xml(self, request):
        sch = etree.Element("Scheduler", version="1.0")

        data = self.scheduler.stats()

        lat = etree.SubElement(sch, "Latency",
                period=str(data['latency']['period']))
        etree.SubElement(lat, "Maximum").text = "%f" % data['latency']['max']
        etree.SubElement(lat, "Minimum").text = "%f" % data['latency']['min']
        etree.SubElement(lat, "Average").text = "%f" % data['latency']['avg']

        tasks = etree.SubElement(sch, 'Tasks',
                count=str(data['tasks']['count']))
        for task_type in data['tasks']:
            if task_type == "count":
                continue
            task_node = etree.SubElement(tasks, task_type,
                count=str(data['tasks'][task_type]['count']))
            for sub_type in data['tasks'][task_type]:
                if sub_type == "count":
                    continue
                etree.SubElement(task_node, task_type, type=sub_type,
                        count=str(data['tasks'][task_type][sub_type]['count']))

        return sch

class Scheduler(object):
    """Run things!"""

    trend = None
    monitor = None

    def __init__(self, config=None,
            rradir=None, rrdcache=None,
            monitor_port=None, **kwargs):

        self._registered = set()
        self._startup = True
        self._shutdown = None
        self._latency = deque([0], 60)
        self._latency_call = None
        self._task_stats = {
                'count': 0,
                'Group': {'count': 0},
                'Test':  {'count': 0},
                'Query': {'count': 0},
            }

        if monitor_port:
            self._monitor_port = monitor_port
            self.monitor = monitor_api.MonitorSite()
            page = SchedulerPage(self)
            self.monitor.includeChild("scheduler", page)

        if rradir:
            self.trend = trend.TrendMaster(rradir, rrdcache)

        tests = self.build_tests(config, **kwargs)
        for testobj in tests:
            self.register(testobj)

        self.prepare()

    def build_tests(self, config, **kwargs):
        raise Exception("unimplemented")

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

        if not self._startup and not self._registered:
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

            if runnable.type in self._task_stats:
                self._task_stats[runnable.type]['count'] += 1
            else:
                self._task_stats[runnable.type] = {'count': 1}

            if runnable.name:
                if runnable.name in self._task_stats[runnable.type]:
                    self._task_stats[runnable.type][runnable.name]['count'] += 1
                else:
                    self._task_stats[runnable.type][runnable.name] = {'count': 1}

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
        assert self._startup and not self._shutdown

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
        assert not self._startup and not self._shutdown
        self._shutdown = deferred = defer.Deferred()

        if not self._registered:
            self.stop()
            return deferred

        if self.monitor:
            reactor.listenTCP(self._monitor_port, self.monitor)

        if len(self._registered) == 1:
            # Only running one test, skip the fancy stuff
            reactor.callLater(0, list(self._registered)[0].start)
            return deferred

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
        self._latency_call = reactor.callLater(1.0, self.latency, time.time())

        log.info("Startup complete, running...")
        return deferred

    def stop(self):
        """Stop the scheduler"""
        assert self._shutdown

        if self._registered:
            log.warn("Stopping while still active!")
        else:
            log.info("Nothing left to do, stopping.")

        if self._latency_call:
            self._latency_call.cancel()
            self._latency_call = None

        deferred = self._shutdown
        self._shutdown = None
        deferred.callback(None)

    def latency(self, last):
        now = time.time()
        self._latency_call = reactor.callLater(1.0, self.latency, now)

        latency = now - last - 1.0
        self._latency.append(latency)

        if latency > 5.0:
            log.error("Callback latency: %s" % latency)
        elif latency > 1.5:
            log.warn("Callback latency: %s" % latency)

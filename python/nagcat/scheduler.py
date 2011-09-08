# Copyright 2008-2010 ITA Software, Inc.
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
import MySQLdb
from collections import deque

from twisted.internet import defer, reactor, task

try:
    from lxml import etree
except ImportError:
    etree = None

from nagcat import log, monitor_api, query, test, trend
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
            monitor_port=None,merlin_db_info={}, **kwargs):

        self._registered = set()
        self._group_index = {}
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
        self._merlin_db_info = merlin_db_info

        if monitor_port:
            self._monitor_port = monitor_port
            self.monitor = monitor_api.MonitorSite()
            page = SchedulerPage(self)
            self.monitor.includeChild("scheduler", page)

        if rradir:
            self.trend = trend.TrendMaster(rradir, rrdcache)

        self.query = query.QueryManager(self)

        self.build_tests(config, **kwargs)

        self._test_index = 0

        self._peer_id = None
        self._peer_id_timestamp = None
        self._num_peers = None
        self._update_peer_id()

    def _set_peer_id_and_timestamp(self):
                try:
                    db = MySQLdb.connect(
                        user=self._merlin_db_info['merlin_db_user'],
                        host=self._merlin_db_info['merlin_db_host'],
                        passwd=self._merlin_db_info['merlin_db_pass'],
                        db=self._merlin_db_info['merlin_db_name'])
                    curs = db.cursor()
                    num_rows = curs.execute(
                        """select * from merlin_peers where state=3;""")
                    self._num_peers = num_rows
                    for i in range(num_rows):
                        row = curs.fetchone()
                        if row[0] == "localhost":
                            self._peer_id = row[5]
                            self._peer_id_timestamp = time.time()
                except:
                    log.error("Unable to get peer_id")
    def _update_peer_id(self):
        log.debug("Updating peer_id with _merlin_db_info=%s", self._merlin_db_info)
        if self._peer_id and self._peer_id_timestamp:
            if time.time() - self._peer_id_timestamp >= 60:
                # peer_id should be refreshed.
                self._set_peer_id_and_timestamp()
            else:
                # peer_id is still valid, return.
                return
        else: # We are missing peer_id or peer_id_timestamp...
            if self._merlin_db_info:
                self._set_peer_id_and_timestamp()

    def get_peer_id(self):
        self._update_peer_id()
        log.debug("Seeting _peer_id = %s", self._peer_id)
        return self._peer_id

    def get_num_peers(self):
        self._update_peer_id()
        log.debug("Seeting num_peers = %s", self._num_peers)
        return self._num_peers



    def build_tests(self, config, **kwargs):
        raise Exception("unimplemented")

    def new_test(self, config):
        new = test.Test(self, config, self._test_index)
        self._test_index += 1
        self.register(new)
        if self.trend:
            self.trend.setup_test_trending(new, config)
        return new

    def new_query(self, config, qcls=None):
        return self.query.new_query(config, qcls)

    def register(self, task):
        """Register a top level Runnable to be run directly by the scheduler"""
        assert self._startup
        assert task not in self._group_index
        assert isinstance(task, Runnable)

        log.trace("Registering task %s", task)

        task_deps = task.getAllDependencies()
        groups = set(g for g in (self._group_index.get(d, None)
                for d in task_deps) if g and g.repeat <= task.repeat)

        update_index = set(task_deps)
        update_index.add(task)

        if not groups:
            group = RunnableGroup([task])
            self._update_stats(group)
            self._registered.add(group)
            log.trace("Created group %s", group)
        else:
            group = groups.pop()
            group.addDependency(task)
            log.trace("Updated group %s", group)
            for extra_group in groups:
                self._update_stats(extra_group, -1)
                self._registered.remove(extra_group)
                group.addDependencies(extra_group)
                update_index.update(extra_group.getAllDependencies())
                log.trace("Merged group %s", extra_group)

        for runnable in update_index:
            if runnable not in self._group_index:
                self._update_stats(runnable)
            self._group_index[runnable] = group

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

    def _update_stats(self, runnable, inc=1):
        """Record a previously unknown runnable"""

        self._task_stats['count'] += inc

        if runnable.type in self._task_stats:
            self._task_stats[runnable.type]['count'] += inc
        else:
            self._task_stats[runnable.type] = {'count': inc}

        if runnable.name:
            if runnable.name in self._task_stats[runnable.type]:
                self._task_stats[runnable.type][runnable.name]['count'] += inc
            else:
                self._task_stats[runnable.type][runnable.name] = {'count': inc}

    def _log_stats(self):
        """Report the number of tasks"""

        log.info("Tasks: %s", self._task_stats['count'])
        log.info("Groups: %s", self._task_stats['Group']['count'])
        log.info("Tests: %s", self._task_stats['Test']['count'])
        log.info("Queries: %s", self._task_stats['Query']['count'])
        for query_type, query_info in self._task_stats['Query'].iteritems():
            if query_type == "count":
                continue
            log.info("Query %s: %s", query_type, query_info['count'])

    def start(self):
        """Start up the scheduler!"""
        assert self._startup and not self._shutdown
        self._startup = False
        self._shutdown = deferred = defer.Deferred()
        del self._group_index

        if not self._registered:
            self.stop()
            return deferred

        if self.monitor:
            reactor.listenTCP(self._monitor_port, self.monitor)

        self._log_stats()

        # Collect runnables that query the same host so that we can
        # avoid hitting a host with many queries at once
        host_groups = {}
        for runnable in self._registered:
            runnable.finalize()
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
                self.schedule(runnable, delay)
                delay += slot

        # Start latency self-checker
        self._latency_call = reactor.callLater(1.0, self.latency, time.time())

        log.info("Startup complete, running...")
        return deferred

    def schedule(self, runnable, delay=None):
        """(re)schedule a top level runnable"""
        if delay is None:
            delay = runnable.repeat

        if not delay:
            log.error("Task %s has no repeat value.", runnable)
        else:
            log.debug("Scheduling %s in %s seconds.", runnable, delay)
            deferred = task.deferLater(reactor, delay, runnable.start)
            deferred.addBoth(lambda x: self.schedule(runnable))

    def stop(self):
        """Stop the scheduler"""
        assert self._shutdown

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

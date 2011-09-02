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

import time
import socket
import _mysql

from twisted.internet import defer, reactor, task
from twisted.python import failure
from coil.struct import Struct

from nagcat import errors, util, log

class Runnable(object):
    """This class is used for starting various processing chunks such
    as tests and queries. Any child of this class will likely want to
    override _start to actually run its task.
    """

    # This defines how the monitor page reports this object
    type = "Runnable"

    # Similar but only used for Query objects right now
    name = None

    def __init__(self, conf, merlin_db_info={}):
        self.__depends = set()
        self.lastrun = 0
        self.result = None
        self.deferred = None
        self.merlin_db_info = merlin_db_info
        self._set_peer_id()

        assert isinstance(conf, Struct)
        conf.expand(recursive=False)

        self.label = conf.get('label', "")
        self.host = conf.get('host', None)
        self.description = conf.get('description', '')
        # self.task_number is the number of the task in an ordered list
        # of all tasks. This is used to implement the merlin load balancing
        # algorithm. If it is None, no load balancing will be used.
        self.task_number = conf.get('task_number', None)

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

    def finalize(self):
        pass

    def _start(self):
        """Start a Runnable object, return a Deferred.
        
        Override this method when subclassing.
        Do not call this method directly.
        """
        return defer.succeed(None)

    def _start_dependencies(self):
        if self.__depends:
            log.debug("Starting dependencies for %s", self)
            deferlist = []
            for dep in self.__depends:
                deferlist.append(dep.start())
            return defer.DeferredList(deferlist)
        else:
            return defer.succeed(None)

    def _start_self(self):
        log.debug("Starting %s", self)
        return task.deferLater(reactor, 0, self._start)

    def _set_peer_id(self):
        """Sets self.peer_id to either a number, or none.
        This is for loadbalancing and integration with Merlin."""
        try:
            db = _mysql.connect(host=self.merlin_db_info['merlin_db_host'],
                                user=self.merlin_db_info['merlin_db_user'],
                                passwd=self.merlin_db_info['merlin_db_pass'],
                                db=self.merlin_db_info['merlin_db_name'])
            # To merlin, a state of 3 means a peer is running
            db.query("""Select * from merlin_peers where state=3;""")
            peers = db.store_result()
            for count in (range(peers.num_rows())):
                row = peers.fetch_row()
                log.debug("A wild merlin peer has appeared!: %s", row)
                # row should look something like the following
                # (('hostname',None,None,'2','3','1'),)
                if row[0][0] == 'localhost':
                    self.peer_id = int(row[0][5])
            log.debug("Merlin peer id: %s", self.peer_id)
        except:
            log.debug("Could not connect to Merlin database")
            self.peer_id = None
        return

    def _set_should_run(self):
        """Decides whether or not a runnable object should be scheduled
        by reading merlin_peers table in the merlin database"""
        self.should_run = True
        log.debug("Host: %s", self.host)
        log.debug("Description: %s", self.description)
        log.debug("peer_id: %s", self.peer_id)
        log.debug("task_number: %s", self.task_number)
        if self.peer_id:
            if self.task_number:
                if not self.peer_id % int(self.task_number)== 0:
                    self.should_run = False

        log.debug("should_run = %s", self.should_run)
        return


    def start(self):
        """Start a Runnable object"""

        # Grab peer_id, it might have changed
        self._set_peer_id()
        # Don't start if we shouldn't run
        self._set_should_run()
        if not self.should_run:
            return

        # Don't start again if we are already running
        if self.deferred is not None:
            return self.deferred

        # Reuse old results if our time isn't up yet
        elif self.lastrun + self.repeat.seconds > time.time():
            log.debug("Skipping start of %s", self)
            return defer.succeed(None)

        else:
            # use deferred instead of self.deferred because
            # __done could have been called already
            self.deferred = deferred = self._start_dependencies()
            deferred.addBoth(lambda x: self._start_self())
            deferred.addBoth(self._done)
            return deferred

    @errors.callback
    def _done(self, result):
        """Save the result, log unhandled errors"""

        log.debug("Stopping %s", self)
        log.debug("Result: %s", result)
        self.result = result
        self.lastrun = time.time()
        self.deferred = None

        if isinstance(result, failure.Failure):
            if isinstance(result.value, errors.TestError):
                if result.tb is not None:
                    log.warn("TestError with a traceback in %s:\n%s" %
                            (self, result.getTraceback()))
            else:
                log.error("Unhandled error in %s:\n%s" %
                        (self, result.getTraceback()))

    def addDependency(self, dep):
        """Declare that self depends on another Runnable"""
        self.__depends.add(dep)

    def addDependencies(self, group):
        """Add a group of dependencies at once"""
        if isinstance(group, Runnable):
            group = group.getDependencies()
        self.__depends.update(group)

    def delDependency(self, dep):
        """Remove a dependency"""
        self.__depends.remove(dep)

    def hasDependencies(self):
        """Return True if this task has dependencies"""
        return bool(self.__depends)

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

    type = "Group"

    def __init__(self, group):
        conf = Struct({'repeat': None, 'host': None, 'addr': None})
        Runnable.__init__(self, conf)
        for dependency in group:
            self.addDependency(dependency)

    def finalize(self):
        # Grab the first non-zero repeat value and count hosts
        hosts = {}
        for dependency in self.getDependencies():
            if not self.repeat:
                self.repeat = dependency.repeat

            if dependency.host in hosts:
                hosts[dependency.host] += 1
            else:
                hosts[dependency.host] = 1

        # Select the most common host in the group for this group's host
        # this is used to distribute queries to a host evenly.
        max_count = 0
        for host, count in hosts.iteritems():
            if count > max_count:
                self.host = host
                max_count = count

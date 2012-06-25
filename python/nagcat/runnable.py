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

    def __init__(self, conf):
        self.__depends = set()
        self.lastrun = 0
        self.result = None
        self.deferred = None

        assert isinstance(conf, Struct)
        conf.expand(recursive=False)

        self.label = conf.get('label', "")
        self.host = conf.get('host', None)
        self._private = conf.get('private', False)

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

    def private(self):
        """True if this or any of its dependencies have a private config."""

        if self._private:
            return True
        elif any(dep.private() for dep in self.getDependencies()):
            self._private = True
            return True
        else:
            return False

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

    def start(self):
        """Start a Runnable object"""

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

    def __init__(self, group, repeat):
        conf = Struct({'repeat': repeat, 'host': None, 'addr': None})
        Runnable.__init__(self, conf)
        for dependency in group:
            self.addDependency(dependency)

    def addDependency(self, dep):
        assert dep.repeat == self.repeat
        super(RunnableGroup, self).addDependency(dep)

    def addDependencies(self, group):
        assert all(d.repeat == self.repeat for d in group.getDependencies())
        super(RunnableGroup, self).addDependencies(group)

    def finalize(self):
        # Grab the first non-zero repeat value and count hosts
        hosts = {}
        for dependency in self.getDependencies():
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

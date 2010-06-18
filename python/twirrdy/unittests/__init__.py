# Copyright 2010 ITA Software, Inc.
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

import os
from twisted.internet import defer, error, protocol, reactor
from twisted.protocols import basic
from twisted.python import log
from twisted.trial import unittest

from twirrdy import RRDBasicAPI

class DummyCacheProtocol(basic.LineOnlyReceiver, object):

    delimiter = '\n'

    def lineReceived(self, line):
        log.msg("SERVER GOT LINE: %r" % line)
        cmd = line.split(None, 1)[0]
        handler = getattr(self, "do_%s" % cmd.upper(), None)
        if handler:
            try:
                handler(line)
            except Exception, ex:
                self.sendLine("-1 %s: %s" % (ex.__class__.__name__, ex))
        else:
            self.sendLine("-1 Unknown command: %s" % cmd)

    def sendLine(self, line):
        super(DummyCacheProtocol, self).sendLine(line)
        log.msg("SERVER SENT LINE: %r" % line)

    def do_TEST(self, line):
        self.sendLine("0 Success")

    def do_STATS(self, line):
        for line in ("9 Statistics follow",
                     "QueueLength: 0",
                     "UpdatesReceived: 30",
                     "FlushesReceived: 2",
                     "UpdatesWritten: 13",
                     "DataSetsWritten: 390",
                     "TreeNodesNumber: 13",
                     "TreeDepth: 4",
                     "JournalBytes: 190",
                     "JournalRotate: 0"):
            self.sendLine(line)

    def do_QUIT(self, line):
        self.transport.loseConnection()

class DummyCacheServer(protocol.ServerFactory, object):

    protocol = DummyCacheProtocol

class UpdateCacheProtocol(DummyCacheProtocol):
    """Like the dummy, but actually updates"""

    def __init__(self):
        self.api = RRDBasicAPI()

    def do_FLUSH(self, line):
        self.sendLine("0 Success")

    def do_PENDING(self, line):
        self.sendLine("0 Success")

    def do_UPDATE(self, line):
        line = line.split()
        assert len(line) == 3
        path = line[1]
        args = line[2].split(':')
        timestamp = args.pop(0)
        log.msg("SERVER UPDATING: %s" % path)
        self.api.update(path, timestamp, args)
        self.sendLine("0 Success")

class UpdateCacheServer(protocol.ServerFactory, object):

    protocol = UpdateCacheProtocol

class LoggingProcessProtocol(protocol.ProcessProtocol):
    """For running the real rrdcached"""

    def __init__(self, started, stopped):
        self._started = started
        self._stopped = stopped

    def outReceived(self, data):
        log.msg("rrdcached: %r" % data)
        if "listening for connections" in data:
            self._started.callback(None)
            self._started = None

    def errReceived(self, data):
        self.outReceived(data)

    def processEnded(self, reason):
        log.msg("rrdcached exited: %s" % reason.value)
        if self._started:
            self._started.errback(reason)
            self._started = None
        self._stopped.errback(reason)
        self._stopped = None

class RealCacheServer(object):
    """Start and stop rrdcached"""

    def __init__(self, address, pidfile):
        self.daemon = os.environ.get('RRDCACHED_PATH', 'rrdcached')
        self.cwd = os.getcwd()
        self.address = os.path.join(self.cwd, address)
        self.pidfile = os.path.join(self.cwd, pidfile)

    def startListening(self):
        def startup_failed(result):
            log.msg("skipping test")
            raise unittest.SkipTest("unable to start rrdcached")

        def filter_done(result):
            if isinstance(result.value, error.ProcessDone):
                return None
            else:
                return result

        args = [self.daemon, '-g',
                '-p', self.pidfile,
                '-l', self.address,
                '-b', self.cwd]
        started = defer.Deferred()
        started.addErrback(startup_failed)
        self.stopped = defer.Deferred()
        self.stopped.addErrback(filter_done)
        proto = LoggingProcessProtocol(started, self.stopped)
        self.proc = reactor.spawnProcess(proto, self.daemon, args)
        return started

    def stopListening(self):
        self.proc.signalProcess(15)
        deferred = self.stopped
        self.stopped = None
        return deferred

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

from twisted.internet import protocol
from twisted.protocols import basic
from twisted.python import log

class DummyCacheProtocol(basic.LineOnlyReceiver, object):

    delimiter = '\n'

    def lineReceived(self, line):
        log.msg("SERVER GOT LINE: %r" % line)
        cmd = line.split(None, 1)[0]
        handler = getattr(self, "do_%s" % cmd.upper(), None)
        if handler:
            handler(line)
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

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

from twisted.internet import defer, error, reactor
from twisted.protocols import loopback
from twisted.python import failure
from twisted.trial import unittest

from twirrdy import protocol
from twirrdy.unittests import DummyCacheProtocol, DummyCacheServer

class ProtocolTestCase(unittest.TestCase):

    def setUp(self):
        self.server = DummyCacheProtocol()
        self.client = protocol.RRDCacheProtocol()
        loopback.loopbackAsync(self.server, self.client)

    def tearDown(self):
        def check(result):
            self.assertIsInstance(result, failure.Failure)
            self.assertIsInstance(result.value, error.ConnectionDone)

        d = self.client.sendLine("QUIT")
        d.addBoth(check)
        return d

    def testSimpleCommand(self):
        d = self.client.sendLine("TEST COMMAND")
        d.addBoth(lambda x: self.assertEquals(x, "0 Success"))
        return d

    def testStatCommand(self):
        def check(result):
            lines = result.split('\n')
            self.assertEquals(lines[0], "9 Statistics follow")
            # header + 9 stats lines
            self.assertEquals(len(lines), 10)

        d = self.client.sendLine("STATS")
        d.addBoth(check)
        return d

    def testManyCommands(self):
        dlist = []
        for x in xrange(10):
            d = self.client.sendLine("TEST COMMAND")
            d.addBoth(lambda x: self.assertEquals(x, "0 Success"))
            dlist.append(d)
        return defer.DeferredList(dlist)

    def testUnknownCommand(self):
        def check(result):
            self.assertIsInstance(result, failure.Failure)
            self.assertIsInstance(result.value, protocol.RRDCacheError)

        d = self.client.sendLine("UNKNOWN COMMAND")
        d.addBoth(check)
        return d

    def testManyUnknownCommands(self):
        def check(result):
            self.assertIsInstance(result, failure.Failure)
            self.assertIsInstance(result.value, protocol.RRDCacheError)

        dlist = []
        for x in xrange(10):
            d = self.client.sendLine("UNKNOWN COMMAND")
            d.addBoth(check)
            dlist.append(d)

        return defer.DeferredList(dlist)

class FactoryTestCase(unittest.TestCase):

    def setUp(self):
        sock = self.mktemp()
        serverfactory = DummyCacheServer()
        self.server = reactor.listenUNIX(sock, serverfactory)
        deferred = defer.Deferred()
        self.client = protocol.RRDCacheClient(deferred, True)
        reactor.connectUNIX(sock, self.client)
        return deferred

    def tearDown(self):
        def check(result):
            self.assertIsInstance(result, failure.Failure)
            self.assertIsInstance(result.value, error.ConnectionDone)

        self.client.stopTrying()
        d = self.client.sendLine("QUIT")
        d.addBoth(check)
        d.addBoth(lambda x: self.server.stopListening())
        return d

    def testSimpleCommand(self):
        d = self.client.sendLine("TEST COMMAND")
        d.addBoth(lambda x: self.assertEquals(x, "0 Success"))
        return d

    def testReconnect(self):
        final = defer.Deferred()

        def check_closed(result):
            self.assertIsInstance(result, failure.Failure)
            self.assertIsInstance(result.value, error.ConnectionDone)

        def setup_reconnect(result):
            self.assertEquals(result, "0 Success")
            self.client._deferred = final
            self.client.maxDelay = 0.1
            d = self.client.sendLine("QUIT")
            d.addBoth(check_closed)
            d.addCallback(lambda x: final)
            d.addCallback(test_reconnect)
            return d

        def test_reconnect(result):
            d = self.client.sendLine("TEST COMMAND")
            d.addCallback(lambda x: self.assertEquals(x, "0 Success"))
            return d

        d = self.client.sendLine("TEST COMMAND")
        d.addCallback(setup_reconnect)
        return d

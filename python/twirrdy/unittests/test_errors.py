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
import shutil
import tempfile

from twisted.internet import defer, reactor
from twisted.python import failure
from twisted.trial import unittest

from twirrdy import RRDBasicAPI, RRDToolError, twist
from twirrdy.unittests import UpdateCacheServer, RealCacheServer

class BasicTestCase(unittest.TestCase):

    def setUp(self):
        self.api = self.mkAPI()
        self.path = self.mktemp()

    def mkAPI(self):
        return RRDBasicAPI()

    def check(self, call, *args):
        self.assertRaises(RRDToolError, call, *args)

    def testInfo(self):
        self.check(self.api.info, self.path)

    def testLastUpdate(self):
        self.check(self.api.lastupdate, self.path)

    def testUpdate(self):
        self.check(self.api.update, self.path, 1, [1])

class TwistSyncTestCase(BasicTestCase):

    def mkAPI(self):
        return twist.RRDTwistedAPI(defer=False)

class TwistAsyncTestCase(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.api = yield self.mkAPI()
        self.path = self.mktemp()

    def mkAPI(self):
        return twist.RRDTwistedAPI()

    def check(self, result):
        self.assertIsInstance(result, failure.Failure)
        self.assertIsInstance(result.value, RRDToolError)

    def testInfo(self):
        deferred = self.api.info(self.path)
        deferred.addBoth(self.check)
        return deferred

    def testLastUpdate(self):
        deferred = self.api.lastupdate(self.path)
        deferred.addBoth(self.check)
        return deferred

    def testUpdate(self):
        deferred = self.api.update(self.path, 1, [1])
        deferred.addBoth(self.check)
        return deferred

class TwistCacheFakedTestCase(TwistAsyncTestCase):

    def mkAPI(self):
        sock = self.mktemp()
        serverfactory = UpdateCacheServer()
        self.server = reactor.listenUNIX(sock, serverfactory)
        api = twist.RRDTwistedAPI()
        deferred = api.open(sock)
        deferred.addCallback(lambda x: api)
        return deferred

    def tearDown(self):
        d = self.api.close()
        d.addBoth(lambda x: self.server.stopListening())
        return d

class TwistCacheTestTestCase(TwistCacheFakedTestCase):
    # FIXME: This is copied from test_api, if this code is ever changed it
    # should be re-organized to kill the copy but it works right now so meh

    def mkAPI(self):
        # We can't reliably put the socket inside the _trial_temp working
        # directory because that tends to be longer than 108 bytes, /tmp works
        self.tmpdir = tempfile.mkdtemp(prefix="rrdcached.test.", dir="/tmp")
        sock = os.path.join(self.tmpdir, "rrdcached.sock")
        pidfile = os.path.join(self.tmpdir, "rrdcached.pid")
        self.server = RealCacheServer(sock, pidfile)

        def client_fail(result):
            print "Client fail: %s" % result
            os.system("ps ax | grep rrdcached")
            d = self.server.stopListening()
            d.addBoth(lambda x: result)
            return d

        def client(result):
            api = twist.RRDTwistedAPI()
            deferred = api.open(sock)
            deferred.addCallback(lambda x: api)
            deferred.addErrback(client_fail)
            return deferred

        deferred = self.server.startListening()
        deferred.addCallback(client)
        deferred.addErrback(self.rmtmpdir)
        return deferred

    def rmtmpdir(self, result):
        shutil.rmtree(self.tmpdir)
        return result

    def tearDown(self):
        d = self.api.close()
        d.addBoth(lambda x: self.server.stopListening())
        d.addBoth(self.rmtmpdir)
        return d

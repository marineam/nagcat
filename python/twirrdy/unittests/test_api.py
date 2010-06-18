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
from twisted.trial import unittest

from twirrdy import RRDBasicAPI, twist
from twirrdy.unittests import UpdateCacheServer, RealCacheServer

class BasicTestCase(unittest.TestCase):

    STEP = 60
    DS   = [{'name': "first", 'type': 'GAUGE', 'heartbeat': STEP*2},
            {'name': "second", 'type': 'COUNTER', 'heartbeat': STEP*2}]
    RRA  = [{'cf': 'MIN', 'xff': 0.5, 'pdp_per_row': 1, 'rows': 10},
            {'cf': 'MAX', 'xff': 0.5, 'pdp_per_row': 1, 'rows': 10}]
    DATA = [(1262304000, 100, 1000),
            (1262304066, 99,  1020),
            (1262304124, 106, 1050)]
    START = DATA[0][0] - 10

    @defer.inlineCallbacks
    def setUp(self):
        self.api = yield self.mkAPI()
        self.path = self.mktemp()
        yield self.api.create(self.path, self.DS,
                self.RRA, self.STEP, self.START)

    def mkAPI(self):
        return RRDBasicAPI()

    @defer.inlineCallbacks
    def testInfo(self):
        info = yield self.api.info(self.path)
        self.checkInfo(info, self.path)

    def checkInfo(self, info, path):
        self.assertEquals(info['filename'], path)
        self.assertEquals(info['step'], self.STEP)

        for i, (name, ds) in enumerate(info['ds'].iteritems()):
            orig = self.DS[i]
            self.assertEquals(name, orig['name'])
            self.assertEquals(ds['type'], orig['type'])

        for i, rra in enumerate(info['rra']):
            orig = self.RRA[i]
            self.assertEquals(rra['cf'], orig['cf'])
            self.assertEquals(rra['xff'], orig['xff'])
            self.assertEquals(rra['pdp_per_row'], orig['pdp_per_row'])
            self.assertEquals(rra['rows'], orig['rows'])

    @defer.inlineCallbacks
    def testLastUpdateNoData(self):
        expect = dict((ds['name'],None) for ds in self.DS)
        ds_time, ds_values = yield self.api.lastupdate(self.path)
        self.assertEquals(ds_time, self.START)
        self.assertEquals(ds_values, expect)

    @defer.inlineCallbacks
    def testLastUpdateWithData(self):
        entry_time = self.DATA[0][0]
        entry_data = self.DATA[0][1:]
        expect = dict(zip((ds['name'] for ds in self.DS), entry_data))
        yield self.api.update(self.path, entry_time, entry_data)
        ds_time, ds_values = yield self.api.lastupdate(self.path)
        self.assertEquals(ds_time, entry_time)
        self.assertEquals(ds_values, expect)

    @defer.inlineCallbacks
    def testInfoCreate(self):
        # We should be able duplicate the structure by mixing info/create
        extra = self.mktemp()
        info = yield self.api.info(self.path)
        yield self.api.create(extra, info['ds'], info['rra'],
                              info['step'], self.START)
        info2 = yield self.api.info(extra)
        self.checkInfo(info2, extra)

    @defer.inlineCallbacks
    def testUpdate(self):
        for entry in self.DATA:
            entry_time = entry[0]
            entry_data = entry[1:]
            yield self.api.update(self.path, entry_time, entry_data)
            info = yield self.api.info(self.path)
            self.checkUpdateDS(info, entry_data)

    def checkUpdateDS(self, info, data):
        for i, ds in enumerate(self.DS):
            last = info['ds'][ds['name']]['last_ds']
            self.assertEquals(last, str(data[i]))

class TwistSyncTestCase(BasicTestCase):

    def mkAPI(self):
        return twist.RRDTwistedAPI(defer=False)

class TwistAsyncTestCase(BasicTestCase):

    def mkAPI(self):
        return twist.RRDTwistedAPI()

class TwistCacheFakedTestCase(BasicTestCase):

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

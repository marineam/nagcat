# Copyright 2009 ITA Software, Inc.
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
import time
from twisted.trial import unittest
from nagcat.unittests import dummy_server
from nagcat import errors, query
from coil.struct import Struct
from snapy.netsnmp.unittests import TestCase as SnmpTestCase

class NoOpQueryTestCase(unittest.TestCase):

    def testBasic(self):
        q = query.Query_noop(Struct({'data': "bogus data"}))
        d = q.start()
        d.addBoth(self.endBasic, q)

    def endBasic(self, ignore, q):
        self.assertEquals(q.result, "bogus data")

class HTTPQueryTestCase(unittest.TestCase):

    def setUp(self):
        self.server = dummy_server.randomTCP(dummy_server.HTTP())
        self.config = Struct({'host': "localhost", 'port': self.server.port})

    def testBasic(self):
        q = query.Query_http(self.config)
        d = q.start()
        d.addBoth(self.endBasic, q)
        return d

    def endBasic(self, ignore, q):
        self.assertEquals(q.result, "hello\n")

    def testPost(self):
        config = self.config.copy()
        config['data'] = "post data"
        q = query.Query_http(config)
        d = q.start()
        d.addBoth(self.endPost, q)
        return d

    def endPost(self, ignore, q):
        self.assertEquals(q.result, "post data")
        
    def tearDown(self):
        return self.server.loseConnection()


class HTTPEmptyResponseTestCase(unittest.TestCase):
    """Test handling of an empty response from an http request"""
    
    def setUp(self):
        self.bad_server = dummy_server.randomTCP(dummy_server.QuickShutdown())
        self.bad_config = Struct({'host': "localhost", 'port': self.bad_server.port})

    def testEmpty(self):
        """test connecting to an HTTP socket that immediately closes"""
        q = query.Query_http(self.bad_config)
        d = q.start()
        d.addBoth(self.endEmpty, q)
        return d

    def endEmpty(self, ignore, q):
        self.assertIsInstance(q.result, errors.Failure)

    def tearDown(self):
        return self.bad_server.loseConnection()


class TCPQueryTestCase(unittest.TestCase):

    def setUp(self):
        self.server = dummy_server.randomTCP(dummy_server.TCP())
        self.config = Struct({'host': "localhost", 'port': self.server.port})

    def testBasic(self):
        q = query.Query_tcp(self.config)
        d = q.start()
        d.addBoth(self.endBasic, q)
        return d

    def endBasic(self, ignore, q):
        self.assertEquals(q.result, "hello\n")

    def testPost(self):
        config = self.config.copy()
        config['data'] = "post data"
        q = query.Query_tcp(config)
        d = q.start()
        d.addBoth(self.endPost, q)
        return d

    def endPost(self, ignore, q):
        self.assertEquals(q.result, "post data")

    def tearDown(self):
        return self.server.loseConnection()

class SubprocessQueryTestCase(unittest.TestCase):

    def testBasic(self):
        q = query.Query_subprocess(Struct({'command': "echo hello"}))
        d = q.start()
        d.addBoth(self.endBasic, q)
        return d

    def endBasic(self, ignore, q):
        self.assertEquals(q.result, "hello\n")

    def testTrue(self):
        q = query.Query_subprocess(Struct({'command': "true"}))
        d = q.start()
        d.addBoth(self.endTrue, q)
        return d

    def endTrue(self, ignore, q):
        self.assertEquals(q.result, "")

    def testFalse(self):
        q = query.Query_subprocess(Struct({'command': "false"}))
        d = q.start()
        d.addBoth(self.endFalse, q)
        return d

    def endFalse(self, ignore, q):
        self.assertIsInstance(q.result, errors.Failure)
        self.assertIsInstance(q.result.value, errors.TestCritical)

    def testEnvGood(self):
        c = {'command': "test_subprocess_path", 'environment': {
                'PATH': os.path.dirname(__file__) } }
        q = query.Query_subprocess(Struct(c))
        d = q.start()
        d.addBoth(self.endEnvGood, q)
        return d

    def endEnvGood(self, ignore, q):
        self.assertEquals(q.result, "")

    def testEnvBad(self):
        q = query.Query_subprocess(Struct({'command': "test_subprocess_path"}))
        d = q.start()
        d.addBoth(self.endEnvBad, q)
        return d

    def endEnvBad(self, ignore, q):
        self.assertIsInstance(q.result, errors.Failure)
        self.assertIsInstance(q.result.value, errors.TestCritical)

class SnmpQueryTestCaseV1(SnmpTestCase):

    version = "1"

    def setUpSession(self, address):
        assert address.startswith('udp:')
        proto, host, port = address.split(":", 3)
        self.conf = Struct({
                'version': self.version,
                'community': "public",
                'host': host,
                'port': port})

    def tearDownSession(self):
        # Clear out the query list
        query._queries.clear()

    def testBasicGood(self):
        c = self.conf.copy()
        c['oid'] = ".1.3.6.1.4.2.1.1";
        q = query.Query_snmp(c)

        def check(ignore):
            self.assertEquals(q.result, "1")

        d = q.start()
        d.addCallback(check)
        return d

    def testBasicBad(self):
        c = self.conf.copy()
        c['oid'] = ".1.3.6.1.4.2.1";
        q = query.Query_snmp(c)

        def check(ignore):
            self.assertIsInstance(q.result, errors.Failure)
            self.assertIsInstance(q.result.value, errors.TestCritical)

        d = q.start()
        d.addCallback(check)
        return d

    def testSetGood(self):
        c = self.conf.copy()
        c['oid_base'] = ".1.3.6.1.4.2.3";
        c['oid_key']  = ".1.3.6.1.4.2.2";
        c['key'] = 'two'
        q = query.Query_snmp(c)

        def check(ignore):
            self.assertEquals(q.result, "2")

        d = q.start()
        d.addCallback(check)
        return d

class SnmpQueryTestCaseV2c(SnmpQueryTestCaseV1):

    version = "2c"

class NTPTestCase(unittest.TestCase):

    skip = "requires network access"

    def testSimple(self):
        conf = Struct({'type': 'ntp',
                'host': 'pool.ntp.org',
                'port': 123})
        now = time.time()
        q = query.Query_ntp(conf)

        def check(ignore):
            # chop off a bunch of time because they won't be exact
            self.assertEquals(time.time() // 3600,
                    int(q.result) // 3600)

        d = q.start()
        d.addCallback(check)
        return d

    def testRefused(self):
        conf = Struct({'type': 'ntp',
                'host': 'localhost',
                'port': 9})
        now = time.time()
        q = query.Query_ntp(conf)

        def check(ignore):
            self.assertIsInstance(q.result, errors.Failure)
            self.assertIsInstance(q.result.value, errors.TestCritical)

        d = q.start()
        d.addCallback(check)
        return d

    # TODO: test timeout

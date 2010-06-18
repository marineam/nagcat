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
from twisted.internet import reactor
from twisted.trial import unittest
from nagcat.unittests import dummy_server
from nagcat import errors, query, plugin, simple
from coil.struct import Struct
from snapy.netsnmp.unittests import TestCase as SnmpTestCase

class QueryTestCase(unittest.TestCase):

    def setUp(self):
        self.nagcat = simple.NagcatDummy()

class FilteredQueryCase(QueryTestCase):

    def testOk(self):
        config = Struct({
                'type': "noop",
                'data': "something",
            })

        t = query.FilteredQuery(self.nagcat, config)
        d = t.start()
        d.addBoth(self.endOk, t)
        return d

    def endOk(self, result, t):
        self.assertEquals(result, None)
        self.assertEquals(t.result, "something")

    def testWarning(self):
        config = Struct({
                'type': "noop",
                'data': "something",
                'warning': "= something",
            })

        t = query.FilteredQuery(self.nagcat, config)
        d = t.start()
        d.addBoth(self.endWarning, t)
        return d

    def endWarning(self, result, t):
        self.assertEquals(result, None)
        self.assertIsInstance(t.result, errors.Failure)
        self.assertIsInstance(t.result.value, errors.TestWarning)
        self.assertEquals(t.result.result, "something")

    def testCritical(self):
        config = Struct({
                'type': "noop",
                'data': "something",
                'warning': "= something",
                'critical': "= something",
            })

        t = query.FilteredQuery(self.nagcat, config)
        d = t.start()
        d.addBoth(self.endCritical, t)
        return d

    def endCritical(self, result, t):
        self.assertEquals(result, None)
        self.assertIsInstance(t.result, errors.Failure)
        self.assertIsInstance(t.result.value, errors.TestCritical)
        self.assertEquals(t.result.result, "something")

    def testFilterCritical(self):
        config = Struct({
                'type': "noop",
                'data': "something",
                'filters': [ "warning: = something", "critical: = something" ],
            })

        t = query.FilteredQuery(self.nagcat, config)
        d = t.start()
        d.addBoth(self.endCritical, t)
        return d


class NoOpQueryTestCase(QueryTestCase):

    def testBasic(self):
        qcls = plugin.search(query.IQuery, 'noop')
        q = qcls(self.nagcat, Struct({'data': "bogus data"}))
        d = q.start()
        d.addBoth(self.endBasic, q)

    def endBasic(self, ignore, q):
        self.assertEquals(q.result, "bogus data")

class HTTPQueryTestCase(QueryTestCase):

    def setUp(self):
        super(HTTPQueryTestCase, self).setUp()
        self.server = reactor.listenTCP(0, dummy_server.HTTP())
        self.port = self.server.getHost().port
        self.config = Struct({'host': "localhost", 'port': self.port})

    def testBasic(self):
        qcls = plugin.search(query.IQuery, 'http')
        q = qcls(self.nagcat, self.config)
        d = q.start()
        d.addBoth(self.endBasic, q)
        return d

    def endBasic(self, ignore, q):
        self.assertEquals(q.result, "hello\n")

    def testPost(self):
        config = self.config.copy()
        config['data'] = "post data"
        qcls = plugin.search(query.IQuery, 'http')
        q = qcls(self.nagcat, config)
        d = q.start()
        d.addBoth(self.endPost, q)
        return d

    def endPost(self, ignore, q):
        self.assertEquals(q.result, "post data")

    def tearDown(self):
        return self.server.loseConnection()


class HTTPEmptyResponseTestCase(QueryTestCase):
    """Test handling of an empty response from an http request"""

    def setUp(self):
        super(HTTPEmptyResponseTestCase, self).setUp()
        self.bad_server = reactor.listenTCP(0, dummy_server.QuickShutdown())
        self.bad_port = self.bad_server.getHost().port
        self.bad_config = Struct({'host': "localhost", 'port': self.bad_port})

    def testEmpty(self):
        """test connecting to an HTTP socket that immediately closes"""
        qcls = plugin.search(query.IQuery, 'http')
        q = qcls(self.nagcat, self.bad_config)
        d = q.start()
        d.addBoth(self.endEmpty, q)
        return d

    def endEmpty(self, ignore, q):
        self.assertIsInstance(q.result, errors.Failure)

    def tearDown(self):
        return self.bad_server.loseConnection()


class TCPQueryTestCase(QueryTestCase):

    def setUp(self):
        super(TCPQueryTestCase, self).setUp()
        self.server = reactor.listenTCP(0, dummy_server.TCP())
        self.port = self.server.getHost().port
        self.config = Struct({'host': "localhost", 'port': self.port})

    def testBasic(self):
        qcls = plugin.search(query.IQuery, 'tcp')
        q = qcls(self.nagcat, self.config)
        d = q.start()
        d.addBoth(self.endBasic, q)
        return d

    def endBasic(self, ignore, q):
        self.assertEquals(q.result, "hello\n")

    def testPost(self):
        config = self.config.copy()
        config['data'] = "post data"
        qcls = plugin.search(query.IQuery, 'tcp')
        q = qcls(self.nagcat, config)
        d = q.start()
        d.addBoth(self.endPost, q)
        return d

    def endPost(self, ignore, q):
        self.assertEquals(q.result, "post data")

    def tearDown(self):
        return self.server.loseConnection()

class SubprocessQueryTestCase(QueryTestCase):

    def testBasic(self):
        qcls = plugin.search(query.IQuery, 'subprocess')
        q = qcls(self.nagcat, Struct({'command': "echo hello"}))
        d = q.start()
        d.addBoth(self.endBasic, q)
        return d

    def endBasic(self, ignore, q):
        self.assertEquals(q.result, "hello\n")

    def testTrue(self):
        qcls = plugin.search(query.IQuery, 'subprocess')
        q = qcls(self.nagcat, Struct({'command': "true"}))
        d = q.start()
        d.addBoth(self.endTrue, q)
        return d

    def endTrue(self, ignore, q):
        self.assertEquals(q.result, "")

    def testFalse(self):
        qcls = plugin.search(query.IQuery, 'subprocess')
        q = qcls(self.nagcat, Struct({'command': "false"}))
        d = q.start()
        d.addBoth(self.endFalse, q)
        return d

    def endFalse(self, ignore, q):
        self.assertIsInstance(q.result, errors.Failure)
        self.assertIsInstance(q.result.value, errors.TestCritical)

    def testEnvGood(self):
        c = {'command': "test_subprocess_path", 'environment': {
                'PATH': os.path.dirname(__file__) } }
        qcls = plugin.search(query.IQuery, 'subprocess')
        q = qcls(self.nagcat, Struct(c))
        d = q.start()
        d.addBoth(self.endEnvGood, q)
        return d

    def endEnvGood(self, ignore, q):
        self.assertEquals(q.result, "")

    def testEnvBad(self):
        qcls = plugin.search(query.IQuery, 'subprocess')
        q = qcls(self.nagcat, Struct({'command': "test_subprocess_path"}))
        d = q.start()
        d.addBoth(self.endEnvBad, q)
        return d

    def endEnvBad(self, ignore, q):
        self.assertIsInstance(q.result, errors.Failure)
        self.assertIsInstance(q.result.value, errors.TestCritical)

class SnmpQueryTestCaseV1(SnmpTestCase, QueryTestCase):

    version = "1"

    def setUp(self):
        QueryTestCase.setUp(self)
        return SnmpTestCase.setUp(self)

    def setUpSession(self, address):
        assert address.startswith('udp:')
        proto, host, port = address.split(":", 3)
        self.conf = Struct({
                'version': self.version,
                'community': "public",
                'host': host,
                'port': port})

    def testBasicGood(self):
        c = self.conf.copy()
        c['oid'] = ".1.3.6.1.4.2.1.1";
        qcls = plugin.search(query.IQuery, 'snmp')
        q = qcls(self.nagcat, c)

        def check(ignore):
            self.assertEquals(q.result, "1")

        d = q.start()
        d.addCallback(check)
        return d

    def testBasicBad(self):
        c = self.conf.copy()
        c['oid'] = ".1.3.6.1.4.2.1";
        qcls = plugin.search(query.IQuery, 'snmp')
        q = qcls(self.nagcat, c)

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
        qcls = plugin.search(query.IQuery, 'snmp')
        q = qcls(self.nagcat, c)

        def check(ignore):
            self.assertEquals(q.result, "2")

        d = q.start()
        d.addCallback(check)
        return d

class SnmpQueryTestCaseV2c(SnmpQueryTestCaseV1):

    version = "2c"

class NTPTestCase(QueryTestCase):

    if 'NTP_HOST' in os.environ:
        ntp_host = os.environ['NTP_HOST']
    else:
        skip = "Set NTP_HOST to run NTP unit tests."

    def testSimple(self):
        conf = Struct({'type': 'ntp',
                'host': self.ntp_host,
                'port': 123})
        now = time.time()
        qcls = plugin.search(query.IQuery, 'ntp')
        q = qcls(self.nagcat, conf)

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
                'port': 9,
                'timeout': 2})
        now = time.time()
        qcls = plugin.search(query.IQuery, 'ntp')
        q = qcls(self.nagcat, conf)

        def check(ignore):
            self.assertIsInstance(q.result, errors.Failure)
            self.assertIsInstance(q.result.value, errors.TestCritical)

        d = q.start()
        d.addCallback(check)
        return d

    # TODO: test timeout

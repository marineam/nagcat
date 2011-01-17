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

from twisted.internet import reactor
from nagcat.unittests.queries import QueryTestCase
from nagcat.unittests import dummy_server
from nagcat import errors
from coil.struct import Struct


class HTTPQueryTestCase(QueryTestCase):

    def setUp(self):
        super(HTTPQueryTestCase, self).setUp()
        self.server = reactor.listenTCP(0, dummy_server.HTTP())
        self.port = self.server.getHost().port
        self.config = {'type': 'http',
                       'host': "localhost",
                       'port': self.port}

    def testBasic(self):
        d = self.startQuery(self.config)
        d.addBoth(self.assertEquals, "hello\n")
        return d

    def testPost(self):
        d = self.startQuery(self.config, data="post data")
        d.addBoth(self.assertEquals, "post data")
        return d

    def tearDown(self):
        return self.server.loseConnection()


class HTTPEmptyResponseTestCase(QueryTestCase):
    """Test handling of an empty response from an http request"""

    def setUp(self):
        super(HTTPEmptyResponseTestCase, self).setUp()
        self.server = reactor.listenTCP(0, dummy_server.QuickShutdown())
        self.port = self.server.getHost().port
        self.config = {'type': 'http',
                       'host': "localhost",
                       'port': self.port}

    def testEmpty(self):
        """test connecting to an HTTP socket that immediately closes"""
        d = self.startQuery(self.config)
        d.addBoth(self.assertIsInstance, errors.Failure)
        return d

    def tearDown(self):
        return self.server.loseConnection()

class HTTPSQueryTestCase(QueryTestCase):

    def start(self, *args, **kwargs):
        context = dummy_server.ssl_context(*args, **kwargs)
        self.server = reactor.listenSSL(0, dummy_server.HTTP(), context)
        self.port = self.server.getHost().port
        self.config = {'type': 'https',
                       'host': "localhost",
                       'port': self.port}

    def testBasic(self):
        self.start("localhost-a.key", "localhost-a.cert")
        d = self.startQuery(self.config)
        d.addBoth(self.assertEquals, "hello\n")
        return d

    def testVerifyClientBad(self):
        self.start("localhost-a.key", "localhost-a.cert", ["ca.cert"], verify=True)

        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)

        d = self.startQuery(self.config)
        d.addBoth(check)
        return d

    def testVerifyClientGood(self):
        self.start("localhost-a.key", "localhost-a.cert", ["ca.cert"], verify=True)
        config = self.config.copy()
        config['ssl_key'] = dummy_server.ssl_path("localhost-b.key")
        config['ssl_cert'] = dummy_server.ssl_path("localhost-b.cert")
        d = self.startQuery(config)
        d.addBoth(self.assertEquals, "hello\n")
        return d

    def testVerifyServerBad(self):
        self.start("localhost-a.key", "localhost-a.cert")
        config = self.config.copy()
        config['ssl_cacert'] = dummy_server.ssl_path("bogus-ca.cert")

        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)

        d = self.startQuery(config)
        d.addBoth(check)
        return d

    def testVerifyServerGood(self):
        self.start("localhost-a.key", "localhost-a.cert")
        config = self.config.copy()
        config['ssl_cacert'] = dummy_server.ssl_path("ca.cert")
        d = self.startQuery(config)
        d.addBoth(self.assertEquals, "hello\n")
        return d

    def tearDown(self):
        return self.server.loseConnection()

class XMLRPCTestCase(QueryTestCase):

    def setUp(self):
        super(XMLRPCTestCase, self).setUp()
        self.server = reactor.listenTCP(0, dummy_server.HTTP())
        self.port = self.server.getHost().port
        self.config = {'type': 'xmlrpc',
                       'host': 'localhost',
                       'port': self.port}

    def tearDown(self):
        return self.server.loseConnection()

    def testBasic1(self):
        self.config['method'] = 'echo1'
        self.config['params'] = 1
        d = self.startQuery(self.config)
        d.addCallback(self.assertEquals, '1')
        return d

    def testBasic2(self):
        self.config['method'] = 'echo2'
        self.config['params'] = [1,2]
        d = self.startQuery(self.config)
        d.addCallback(self.assertEquals, "[1, 2]")
        return d

    def testDict(self):
        value = {'this': 1, 'that': [2], 'empty': {}}
        def check(result):
            self.assertEquals(eval(result), value)
        self.config['method'] = 'echo1'
        self.config['params'] = Struct(value)
        d = self.startQuery(self.config)
        d.addCallback(check)
        return d

    def testFault(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)
        self.config['method'] = 'fault'
        d = self.startQuery(self.config)
        d.addBoth(check)
        return d

class XMLRPCSTestCase(XMLRPCTestCase):

    def setUp(self):
        QueryTestCase.setUp(self)
        context = dummy_server.ssl_context("localhost-a.key",
                                           "localhost-a.cert")
        self.server = reactor.listenSSL(0, dummy_server.HTTP(), context)
        self.port = self.server.getHost().port
        self.config = {'type': 'xmlrpcs',
                       'host': "localhost",
                       'port': self.port}


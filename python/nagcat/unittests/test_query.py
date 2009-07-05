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
from twisted.trial import unittest
from nagcat.unittests import dummy_server
from nagcat import errors, query
from coil.struct import Struct

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



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
from nagcat import errors, query, plugin
from coil.struct import Struct


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

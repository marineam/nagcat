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


class TCPQueryTestCase(QueryTestCase):

    def setUp(self):
        super(TCPQueryTestCase, self).setUp()
        self.server = reactor.listenTCP(0, dummy_server.TCP())
        self.port = self.server.getHost().port
        self.config = {'type': "tcp", 'host': "localhost", 'port': self.port}

    def testBasic(self):
        d = self.startQuery(self.config)
        d.addCallback(self.assertEquals, "hello\n")
        return d

    def testPost(self):
        d = self.startQuery(self.config, data="post data")
        d.addCallback(self.assertEquals, "post data")
        return d

    def tearDown(self):
        return self.server.loseConnection()

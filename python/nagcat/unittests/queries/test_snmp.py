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

from nagcat.unittests.queries import QueryTestCase
from nagcat import errors
from snapy.netsnmp.unittests import TestCase as SnmpTestCase


class SnmpQueryTestCaseV1(SnmpTestCase, QueryTestCase):

    version = "1"

    def setUp(self):
        QueryTestCase.setUp(self)
        return SnmpTestCase.setUp(self)

    def setUpSession(self, address):
        assert address.startswith('udp:')
        proto, host, port = address.split(":", 3)
        self.conf = {
                'type': "snmp",
                'version': self.version,
                'community': "public",
                'host': host,
                'port': port}

    def testBasicGood(self):
        d = self.startQuery(self.conf, oid=".1.3.6.1.4.2.1.1")
        d.addCallback(self.assertEquals, "1")
        return d

    def testBasicBad(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)

        d = self.startQuery(self.conf, oid=".1.3.6.1.4.2.1")
        d.addBoth(check)
        return d

    def testSetGood(self):
        d = self.startQuery(self.conf,
                oid_base=".1.3.6.1.4.2.3",
                oid_key=".1.3.6.1.4.2.2",
                key="two")
        d.addCallback(self.assertEquals, "2")
        return d


class SnmpQueryTestCaseV2c(SnmpQueryTestCaseV1):

    version = "2c"

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
from nagcat.unittests.queries import QueryTestCase
from nagcat import errors, query, plugin
from coil.struct import Struct


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
        c = {'command': "simple_subprocess", 'environment': {
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
        q = qcls(self.nagcat, Struct({'command': "simple_subprocess"}))
        d = q.start()
        d.addBoth(self.endEnvBad, q)
        return d

    def endEnvBad(self, ignore, q):
        self.assertIsInstance(q.result, errors.Failure)
        self.assertIsInstance(q.result.value, errors.TestCritical)

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
from nagcat import errors


class SubprocessQueryTestCase(QueryTestCase):

    def testBasic(self):
        d = self.startQuery(type='subprocess', command='echo hello')
        d.addCallback(self.assertEquals, "hello\n")
        return d

    def testTrue(self):
        d = self.startQuery(type='subprocess', command='true')
        d.addCallback(self.assertEquals, "")
        return d

    def testFalse(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)

        d = self.startQuery(type='subprocess', command='false')
        d.addBoth(check)
        return d

    def testEnvGood(self):
        c = {'type': "subprocess",
             'command': "simple_subprocess",
             'environment': {
                'PATH': os.path.dirname(__file__) } }
        d = self.startQuery(c)
        d.addCallback(self.assertEquals, "")
        return d

    def testEnvBad(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)

        d = self.startQuery(type='subprocess', command='simple_subprocess')
        d.addBoth(check)
        return d

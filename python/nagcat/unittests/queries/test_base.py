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

from nagcat import errors, query
from nagcat.unittests.queries import QueryTestCase
from coil.struct import Struct


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
        d = self.startQuery(type="noop", data="bogus data")
        d.addBoth(self.assertEquals, "bogus data")
        return d

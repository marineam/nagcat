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

from twisted.trial import unittest
#from nagcat.unittests import dummy_server
from coil.struct import Struct
from nagcat import simple, runnable


class SchedulerTestCase(unittest.TestCase):

    def testSimpleGrouping(self):
        s = simple.NagcatDummy()
        r1 = runnable.Runnable(Struct({'repeat': 60}))
        r2 = runnable.Runnable(Struct({'repeat': 60}))
        r3 = runnable.Runnable(Struct({'repeat': 60}))
        r4 = runnable.Runnable(Struct({'repeat': 60}))
        t1 = runnable.Runnable(Struct({'repeat': 60}))
        t1.addDependency(r1)
        t1.addDependency(r2)
        s.register(t1)
        t2 = runnable.Runnable(Struct({'repeat': 60}))
        t2.addDependency(r2)
        s.register(t2)
        t3 = runnable.Runnable(Struct({'repeat': 60}))
        t3.addDependency(r3)
        s.register(t3)
        t4 = runnable.Runnable(Struct({'repeat': 60}))
        t4.addDependency(r4)
        s.register(t4)
        stats = s.stats()
        expect = {'count': 11,
                  'Test': {'count': 0},
                  'Runnable': {'count': 8},
                  'Group': {'count': 3},
                  'Query': {'count': 0}}
        self.assertEquals(stats['tasks'], expect)

    def testMismatchGrouping(self):
        s = simple.NagcatDummy()
        r1 = runnable.Runnable(Struct({'repeat': 60}))
        t1 = runnable.Runnable(Struct({'repeat': 3600}))
        t1.addDependency(r1)
        s.register(t1)
        t2 = runnable.Runnable(Struct({'repeat': 60}))
        t2.addDependency(r1)
        s.register(t2)
        t3 = runnable.Runnable(Struct({'repeat': 3600}))
        t3.addDependency(r1)
        s.register(t3)
        stats = s.stats()
        expect = {'count': 6,
                  'Test': {'count': 0},
                  'Runnable': {'count': 4},
                  'Group': {'count': 2},
                  'Query': {'count': 0}}
        self.assertEquals(stats['tasks'], expect)

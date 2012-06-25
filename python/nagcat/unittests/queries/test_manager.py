# Copyright 2012 Google Inc.
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

from nagcat import errors, query, simple, util
from coil.struct import Struct
from twisted.trial import unittest


class ManagerTestCase(unittest.TestCase):

    def setUp(self):
        self.nagcat = simple.NagcatDummy()
        self.assertIsInstance(self.nagcat.query, query.QueryManager)

    def testDifferent(self):
        q1 = self.nagcat.new_query(Struct({'type': 'noop', 'data': 'q1'}))
        q2 = self.nagcat.new_query(Struct({'type': 'noop', 'data': 'q2'}))
        self.assertFalse(q1 is q2)

    def testReuse(self):
        q1 = self.nagcat.new_query(Struct({'type': 'noop', 'data': 'q1'}))
        q2 = self.nagcat.new_query(Struct({'type': 'noop', 'data': 'q1'}))
        self.assertTrue(q1 is q2)

    def testRepeatSlower(self):
        q1 = self.nagcat.new_query(Struct({'type': 'noop',
                                           'data': 'q1',
                                           'repeat': '1m'}))
        q2 = self.nagcat.new_query(Struct({'type': 'noop',
                                           'data': 'q1',
                                           'repeat': '1h'}))
        self.assertTrue(q1 is q2)
        self.assertEquals(q1.repeat, util.Interval('1m'))

    def testRepeatFaster(self):
        q1 = self.nagcat.new_query(Struct({'type': 'noop',
                                           'data': 'q1',
                                           'repeat': '1h'}))
        q2 = self.nagcat.new_query(Struct({'type': 'noop',
                                           'data': 'q1',
                                           'repeat': '1m'}))
        self.assertTrue(q1 is q2)
        self.assertEquals(q1.repeat, util.Interval('1m'))

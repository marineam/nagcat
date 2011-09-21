# Copyright 2011 Google, Inc.
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
from nagcat import merlin, merlintest
from coil.struct import Struct
import os

class TestMerlinTestCase(unittest.TestCase):

    def testMerlinTestDontRun(self):
        config = Struct({
                'query': {
                    'type': "compound",
                    'test-a': {
                        'type': "noop",
                        'data': "1",
                    },
                    'test-b': {
                        'type': "noop",
                        'data': "2",
                    },
                    'return': "$(test-a) + $(test-b)",
                },
            })
        t = merlintest.MerlinTest(merlin.NagcatMerlinDummy(), config, 1)
        d = t.start()
        d.addBoth(self.endMerlinTestRun, t)
        return d

    def endMerlinTestDontRun(self, result, t):
        assertEquals(result, None)
        assertIsNone(t.result['output'])

    def testMerlinTestRun(self):
        config = Struct({
                'query': {
                    'type': "compound",
                    'test-a': {
                        'type': "noop",
                        'data': "1",
                    },
                    'test-b': {
                        'type': "noop",
                        'data': "2",
                    },
                    'return': "$(test-a) + $(test-b)",
                },
            })
        t = merlintest.MerlinTest(merlin.NagcatMerlinDummy(), config, 0)
        d = t.start()
        d.addBoth(self.endMerlinTestRun, t)
        return d

    def endMerlinTestRun(self, result, t):
        self.assertEquals(result, None)
        self.assertEquals(t.result['output'], '3')

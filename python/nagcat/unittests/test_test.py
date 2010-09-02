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
from nagcat import simple, test
from coil.struct import Struct

class TestTestCase(unittest.TestCase):

    def testBasic(self):
        config = Struct({
                'query': {
                    'type': "noop",
                    'data': "something",
                },
            })

        t = test.Test(simple.NagcatDummy(), config)
        d = t.start()
        d.addBoth(self.endBasic, t)
        return d

    def endBasic(self, result, t):
        self.assertEquals(result, None)
        self.assertEquals(t.result['output'], "something")

    def testCompound(self):
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

        t = test.Test(simple.NagcatDummy(), config)
        d = t.start()
        d.addBoth(self.endCompound, t)
        return d

    def endCompound(self, result, t):
        self.assertEquals(result, None)
        self.assertEquals(t.result['output'], "3")

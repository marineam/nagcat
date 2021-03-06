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
from coil.struct import Struct
from nagcat import runnable

class RunnableTestCase(unittest.TestCase):

    def testSingle(self):
        r = runnable.Runnable(Struct({'repeat': None}))
        d = r.start()
        d.addBoth(self.endSingle, r)
        return d

    def endSingle(self, ignore, r):
        self.assertIdentical(r.result, None)

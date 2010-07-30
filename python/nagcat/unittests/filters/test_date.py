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

import time
from twisted.trial import unittest
from nagcat import errors, filters

class DateTestCase(unittest.TestCase):

    def testBasic(self):
        timestamp = str(time.mktime(time.strptime("20050505", "%Y%m%d")))
        f = filters.Filter(object(), "date2epoch:%Y%m%d")
        self.assertEquals(f.filter("20050505"), timestamp)

    def testBad(self):
        f = filters.Filter(object(), "date2epoch:%Y%m%d")
        self.assertIsInstance(f.filter("2005-05-05"), errors.Failure)

    def testDefault(self):
        # Default to 1/1/1900
        f = filters.Filter(object(), "date2epoch[-2208970800]:%Y%m%d")
        self.assertEquals(f.filter("blah"), "-2208970800")

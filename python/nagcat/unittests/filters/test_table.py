# Copyright 2010 ITA Software, Inc.
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
from nagcat import errors, filters

class TableTestCase(unittest.TestCase):

    def setUp(self):
        self.csv = ("foo,bar,baz\n" "biz,buz,lol\n")
        self.pw = ("root:x:0:0:root:/root:/bin/bash\n"
                   "daemon:x:1:1:daemon:/usr/sbin:/bin/sh\n"
                   "bin:x:2:2:bin:/bin:/bin/sh\n")
        self.tab = ("Col1\tCol2\tCol3\n"
                    "foo\tbar\tbaz\n"
                    "biz\tbuz\tlol\n")

    def testTrivial(self):
        f = filters.Filter(object(), "table:0,0")
        self.assertEquals(f.filter("foo,bar"), "foo")

    def testCSV(self):
        f = filters.Filter(object(), "table:1,1")
        self.assertEquals(f.filter(self.csv), "buz")

    def testPasswd(self):
        f = filters.Filter(object(), "table:1,4")
        self.assertEquals(f.filter(self.pw), "daemon")

    def testTab(self):
        f = filters.Filter(object(), "table:1,1")
        self.assertEquals(f.filter(self.tab), "bar")

    def testMissing(self):
        f = filters.Filter(object(), "table:0,4")
        self.assertIsInstance(f.filter("foo,bar"), errors.Failure)
        f = filters.Filter(object(), "table:4,0")
        self.assertIsInstance(f.filter("foo,bar"), errors.Failure)

    def testDefault(self):
        f = filters.Filter(object(), "table[x]:0,4")
        self.assertEquals(f.filter("foo,bar"), "x")
        f = filters.Filter(object(), "table[x]:4,0")
        self.assertEquals(f.filter("foo,bar"), "x")

    def testGetRow(self):
        f = filters.Filter(object(), "table:1")
        self.assertEquals(f.filter(self.csv), "biz,buz,lol")

    def testGetCol(self):
        f = filters.Filter(object(), "table:,1")
        self.assertEquals(f.filter(self.csv), "bar\nbuz")

    def testGetColByName(self):
        f = filters.Filter(object(), "table:1,Col2")
        self.assertEquals(f.filter(self.tab), "bar")

    def testGetRowByName(self):
        f = filters.Filter(object(), "table:daemon,6")
        self.assertEquals(f.filter(self.pw), "/bin/sh")

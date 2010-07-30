# Copyright 2009-2010 ITA Software, Inc.
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

class RegexTestCase(unittest.TestCase):

    def testBasic(self):
        f = filters.Filter(object(), "regex:^foo$")
        self.assertEquals(f.filter("foo"), "foo")
        self.assertIsInstance(f.filter("bar"), errors.Failure)

    def testDefault(self):
        f = filters.Filter(object(), "regex[def]:^foo$")
        self.assertEquals(f.filter("foo"), "foo")
        self.assertEquals(f.filter("bar"), "def")

    def testGroup(self):
        f = filters.Filter(object(), "regex:^(f)(oo)$")
        self.assertEquals(f.filter("foo"), "f")

class GrepTestCase(unittest.TestCase):

    def testNormal(self):
        f = filters.Filter(object(), "grep:^foo$")
        self.assertEquals(f.filter("zoom\nfoo\nbaz"), "foo\n")
        self.assertIsInstance(f.filter("zoom\nbar\nbaz"), errors.Failure)

    def testInverse(self):
        f = filters.Filter(object(), "grepv:^foo$")
        self.assertEquals(f.filter("zoom\nfoo\nbaz"), "zoom\nbaz")
        self.assertIsInstance(f.filter("foo"), errors.Failure)

    def testDefault(self):
        f = filters.Filter(object(), "grep[doh]:^foo$")
        self.assertEquals(f.filter("zoom\nbar\nbaz"), "doh")

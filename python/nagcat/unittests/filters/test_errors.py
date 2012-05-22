# Copyright 2009-2012 ITA Software, Inc.
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

class ExpectCriticalTestCase(unittest.TestCase):

    def testBasic(self):
        f = filters.Filter(object(), "expectcritical:=~^foo$")
        self.assertEquals(f.filter(errors.Failure(errors.TestCritical("foo"))), "Expected Error: foo")
        self.assertRaises(errors.TestCritical, f.filter, errors.Failure(errors.TestCritical("bar")))
        self.assertRaises(errors.TestCritical, f.filter, "foo")

class ExpectWarningTestCase(unittest.TestCase):

    def testBasic(self):
        f = filters.Filter(object(), "expectwarning:=~^foo$")
        self.assertEquals(f.filter(errors.Failure(errors.TestWarning("foo"))), "Expected Error: foo")
        self.assertRaises(errors.TestCritical, f.filter, errors.Failure(errors.TestWarning("bar")))
        self.assertRaises(errors.TestCritical, f.filter, "foo")

class ExpectErrorTestCase(unittest.TestCase):

    def testBasic(self):
        f = filters.Filter(object(), "expecterror:=~^foo$")
        self.assertEquals(f.filter(errors.Failure(errors.TestCritical("foo"))), "Expected Error: foo")
        self.assertRaises(errors.TestCritical, f.filter, errors.Failure(errors.TestCritical("bar")))
        self.assertEquals(f.filter(errors.Failure(errors.TestWarning("foo"))), "Expected Error: foo")
        self.assertRaises(errors.TestCritical, f.filter, errors.Failure(errors.TestWarning("bar")))
        self.assertRaises(errors.TestCritical, f.filter, "foo")

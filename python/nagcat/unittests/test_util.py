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

from __future__ import division

from twisted.trial import unittest
from nagcat import util

class IntervalTestcase(unittest.TestCase):

    def testSeconds(self):
        a = util.Interval("5 Seconds")
        self.assertEquals(a.seconds, 5)
        a = util.Interval("5.5sec")
        self.assertEquals(a.seconds, 5.5)
        a = util.Interval("5 s")
        self.assertEquals(a.seconds, 5)
        a = util.Interval("5")
        self.assertEquals(a.seconds, 5)
        a = util.Interval("5.5")
        self.assertEquals(a.seconds, 5.5)
        a = util.Interval(5)
        self.assertEquals(a.seconds, 5)
        a = util.Interval(5.5)
        self.assertEquals(a.seconds, 5.5)
        a = util.Interval(5)
        b = util.Interval(a)
        self.assertEquals(b.seconds, 5)

    def testMinutes(self):
        a = util.Interval("5 Minutes")
        self.assertEquals(a.seconds, 300)
        a = util.Interval("5.5min")
        self.assertEquals(a.seconds, 330)
        a = util.Interval("5 m")
        self.assertEquals(a.seconds, 300)

    def testHours(self):
        a = util.Interval("5 Hours")
        self.assertEquals(a.seconds, 18000)
        a = util.Interval("5.5 hour")
        self.assertEquals(a.seconds, 19800)
        a = util.Interval("5 h")
        self.assertEquals(a.seconds, 18000)

    def testEq(self):
        a = util.Interval("300 seconds")
        b = util.Interval("5 minutes")
        self.assertEquals(a, b)

    def testBool(self):
        a = util.Interval("")
        b = util.Interval("0s")
        c = util.Interval("5s")
        self.assertEquals(bool(a), False)
        self.assertEquals(bool(b), False)
        self.assertEquals(bool(c), True)

    def testStr(self):
        a = util.Interval("1hour")
        self.assertEquals(str(a), "3600.0 seconds")

class MathStringTestCase(unittest.TestCase):

    def testFloatCast(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertIsInstance(float(a), float)
        self.assertIsInstance(float(b), float)

    def testIntCast(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertIsInstance(int(a), int)
        self.assertIsInstance(int(b), int)

    def testStrCast(self):
        a = util.MathString("string")
        self.assertIsInstance(str(a), str)

    def testAdd(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a + 1, 3)
        self.assertEquals(a + 1.5, 3.5)
        self.assertEquals(a + b, 3.5)
        self.assertEquals(1 + a, 3)
        self.assertEquals(1.5 + a, 3.5)
        self.assertEquals(b + a, 3.5)

    def testSub(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a - 1, 1)
        self.assertEquals(a - 1.5, .5)
        self.assertEquals(a - b, .5)
        self.assertEquals(1 - a, -1)
        self.assertEquals(1.5 - a, -.5)
        self.assertEquals(b - a, -.5)

    def testMul(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a * 1, 2)
        self.assertEquals(a * 1.5, 3.0)
        self.assertEquals(a * b, 3.0)
        self.assertEquals(1 * a, 2)
        self.assertEquals(1.5 * a, 3.0)
        self.assertEquals(b * a, 3.0)

    def testTrueDiv(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a / 1, 2)
        self.assertEquals(a / 1.5, 2/1.5)
        self.assertEquals(a / b, 2/1.5)
        self.assertEquals(1 / a, .5)
        self.assertEquals(1.5 / a, .75)
        self.assertEquals(b / a, .75)

    def testFloorDiv(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a // 1, 2)
        self.assertEquals(a // 1.5, 1.0)
        self.assertEquals(a // b, 1.0)
        self.assertEquals(1 // a, 0)
        self.assertEquals(1.5 // a, 0.0)
        self.assertEquals(b // a, 0.0)

    def testMod(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a % 1, 0)
        self.assertEquals(a % 1.5, .5)
        self.assertEquals(a % b, .5)
        self.assertEquals(1 % a, 1)
        self.assertEquals(1.5 % a, 1.5)
        self.assertEquals(b % a, 1.5)

    def testDivMod(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(divmod(a, 1), (2,0))
        self.assertEquals(divmod(a, 1.5), (1.0, .5))
        self.assertEquals(divmod(a, b), (1.0, .5))
        self.assertEquals(divmod(1, a), (0, 1))
        self.assertEquals(divmod(1.5, a), (0.0, 1.5))
        self.assertEquals(divmod(b, a), (0.0, 1.5))

    def testPow2(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a ** 1, 2)
        self.assertEquals(a ** 1.5, 2 ** 1.5)
        self.assertEquals(a ** b, 2 ** 1.5)
        self.assertEquals(1 ** a, 1)
        self.assertEquals(1.5 ** a, 2.25)
        self.assertEquals(b ** a, 2.25)

    def testPow3(self):
        a = util.MathString("2")
        b = util.MathString("3")
        self.assertEquals(pow(a, 3, 3), 2)
        self.assertEquals(pow(a, b, 3), 2)
        self.assertEquals(pow(a, 3, b), 2)
        # these don't work and I don't know how to make them work :-(
        #self.assertEquals(pow(2, b, 3), 2)
        #self.assertEquals(pow(2, 3, b), 2)
        #self.assertEquals(pow(2, b, b), 2)

    def testNeg(self):
        a = util.MathString("2")
        b = util.MathString("-1.5")
        self.assertEquals(-a, -2)
        self.assertEquals(-b, 1.5)

    def testAbs(self):
        a = util.MathString("2")
        b = util.MathString("-1.5")
        self.assertEquals(abs(a), 2)
        self.assertEquals(abs(b), 1.5)

    def testLt(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a < 1, False)
        self.assertEquals(a < 2, False)
        self.assertEquals(a < b, False)
        self.assertEquals(1 < a, True)
        self.assertEquals(2 < a, False)
        self.assertEquals(b < a, True)

    def testLe(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a <= 1, False)
        self.assertEquals(a <= 2, True)
        self.assertEquals(a <= b, False)
        self.assertEquals(1 <= a, True)
        self.assertEquals(2 <= a, True)
        self.assertEquals(b <= a, True)

    def testGt(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a > 1, True)
        self.assertEquals(a > 2, False)
        self.assertEquals(a > b, True)
        self.assertEquals(1 > a, False)
        self.assertEquals(2 > a, False)
        self.assertEquals(b > a, False)

    def testGe(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a >= 1, True)
        self.assertEquals(a >= 2, True)
        self.assertEquals(a >= b, True)
        self.assertEquals(1 >= a, False)
        self.assertEquals(2 >= a, True)
        self.assertEquals(b >= a, False)

    def testEq(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a == 1, False)
        self.assertEquals(a == 2, True)
        self.assertEquals(a == b, False)
        self.assertEquals(1 == a, False)
        self.assertEquals(2 == a, True)
        self.assertEquals(b == a, False)

    def testNe(self):
        a = util.MathString("2")
        b = util.MathString("1.5")
        self.assertEquals(a != 1, True)
        self.assertEquals(a != 2, False)
        self.assertEquals(a != b, True)
        self.assertEquals(1 != a, True)
        self.assertEquals(2 != a, False)
        self.assertEquals(b != a, True)

    def testEqStr(self):
        a = util.MathString("this")
        b = util.MathString("that")
        self.assertEquals(a == b, False)
        self.assertEquals(a == "this", True)
        self.assertEquals(a == "that", False)

    def testNeStr(self):
        a = util.MathString("this")
        b = util.MathString("that")
        self.assertEquals(a != b, True)
        self.assertEquals(a != "this", False)
        self.assertEquals(a != "that", True)

class TesterTestCase(unittest.TestCase):

    def test_mktest1(self):
        t = util.Tester.mktest("==1")
        self.assertIsInstance(t, util.EvalTester)

    def test_mktest2(self):
        t = util.Tester.mktest("=~1")
        self.assertIsInstance(t, util.RegexTester)

class EvalTesterTestCase(unittest.TestCase):

    def test_eq1(self):
        t = util.EvalTester("=", "this")
        self.assertTrue(t.test("this"))
        self.assertFalse(t.test("that"))

    def test_eq2(self):
        t = util.EvalTester("==", "this")
        self.assertTrue(t.test("this"))
        self.assertFalse(t.test("that"))

    def test_ne1(self):
        t = util.EvalTester("!=", "this")
        self.assertTrue(t.test("that"))
        self.assertFalse(t.test("this"))

    def test_ne2(self):
        t = util.EvalTester("<>", "this")
        self.assertTrue(t.test("that"))
        self.assertFalse(t.test("this"))

    def test_gr(self):
        t = util.EvalTester(">", "1")
        self.assertTrue(t.test("2"))
        self.assertFalse(t.test("-1"))
        self.assertRaises(util.MathError, t.test, "bleh")

    def test_lt(self):
        t = util.EvalTester("<", "1")
        self.assertTrue(t.test("-1"))
        self.assertFalse(t.test("2"))
        self.assertRaises(util.MathError, t.test, "bleh")

    def test_ge(self):
        t = util.EvalTester(">=", "1")
        self.assertTrue(t.test("2"))
        self.assertTrue(t.test("1"))
        self.assertFalse(t.test("-1"))
        self.assertRaises(util.MathError, t.test, "bleh")

    def test_le(self):
        t = util.EvalTester("<=", "1")
        self.assertTrue(t.test("-1"))
        self.assertTrue(t.test("1"))
        self.assertFalse(t.test("2"))
        self.assertRaises(util.MathError, t.test, "bleh")

class RegexTesterTestCase(unittest.TestCase):

    def test_eq(self):
        t = util.RegexTester("=~", "\w+")
        self.assertTrue(t.test("this"))
        self.assertFalse(t.test("----"))

    def test_ne(self):
        t = util.RegexTester("!~", "\w+")
        self.assertTrue(t.test("----"))
        self.assertFalse(t.test("this"))

    def test_bad(self):
        self.assertRaises(util.TesterError, util.RegexTester, "=~", "(bleh")

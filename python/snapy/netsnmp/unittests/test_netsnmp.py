# snapy - a python snmp library
#
# Copyright (C) 2009 ITA Software, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# version 2 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

from twisted.trial import unittest
from snapy.netsnmp.unittests import TestCase
from snapy.netsnmp import Session, SnmpError, SnmpTimeout

class Result(object):
    """Container for async results"""
    value = None

def set_result(value, result):
    result.value = value

class TestSessionV1(TestCase):

    version = "1"
    basics = [
            (".1.3.6.1.4.2.1.1",  1),
            (".1.3.6.1.4.2.1.2", -1),
            (".1.3.6.1.4.2.1.3",  1),
            (".1.3.6.1.4.2.1.4", "test value"),
            ]

    def setUpSession(self, address):
        self.session = Session("-v", self.version, "-c", "public", address)
        self.session.open()

    def tearDownSession(self):
        self.session.close()

    def test_sget(self):
        result = self.session.sget([x for x,v in self.basics])
        self.assertEquals(result, self.basics)

    def test_get(self):
        result = Result()
        self.session.get([x for x,v in self.basics], set_result, result)
        self.session.wait()
        self.assertEquals(result.value, self.basics)

    def test_getnext_single(self):
        """Test a standard walk using just getnext"""

        all = []
        root = ".1.3.6.1.4.2.1"
        oid = root

        while True:
            result = Result()
            self.session.getnext([oid], set_result, result)
            self.session.wait()

            oid, value = result.value[0]
            if value and oid.startswith(root):
                all.append((oid, value))
            else:
                break

        self.assertEquals(all, self.basics)

    def test_getnext_multi(self):
        """In a standard walk only one oid is sent, test the many case"""

        oids = [".1.3.6.1.4.2.1.0",
                ".1.3.6.1.4.2.1.1",
                ".1.3.6.1.4.2.1.2",
                ".1.3.6.1.4.2.1.3"]

        result = Result()
        self.session.getnext(oids, set_result, result)
        self.session.wait()
        self.assertEquals(result.value, self.basics)

    def test_walk1(self):
        result = Result()
        self.session.walk([".1.3.6.1.4.2.1"], set_result, result)
        self.session.wait()
        self.assertEquals(result.value, self.basics)

    def test_walk2(self):
        result = Result()
        self.session.walk([".1.3.6.1.4.2.1.1"], set_result, result)
        self.session.wait()
        self.assertEquals(result.value, [(".1.3.6.1.4.2.1.1", 1)])

class TestSessionV2c(TestSessionV1):

    version = "2c"

    def test_getbulk(self):
        result = Result()
        # Get the first 4 values which should be self.basics
        self.session.getbulk([".1"], 0, 4, set_result, result)
        self.session.wait()
        self.assertEquals(result.value, self.basics)

class TestTimeoutsV1(unittest.TestCase):

    version = "1"

    def setUp(self):
        self.session = Session("-v", self.version, "-c", "public",
                "-r", "0", "-t", "0.1", "udp:127.0.0.1:9")
        self.session.open()

    def test_sget(self):
        self.assertRaises(SnmpError, self.session.sget, [".1.3.6.1.4.2.1.1"])

    def test_get(self):
        result = Result()
        self.session.get([".1.3.6.1.4.2.1.1"], set_result, result)
        self.session.wait()
        assert isinstance(result.value, SnmpTimeout)

    def tearDown(self):
        self.session.close()

class TestTimeoutsV2c(TestTimeoutsV1):

    version = "2c"

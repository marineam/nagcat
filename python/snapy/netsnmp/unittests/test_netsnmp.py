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
from snapy.netsnmp import Session, SnmpError, SnmpTimeout, OID

class Result(object):
    """Container for async results"""
    value = None

def set_result(value, result):
    result.value = value

class TestSessionV1(TestCase):

    version = "1"
    basics = [
            (OID(".1.3.6.1.4.2.1.1"),  1),
            (OID(".1.3.6.1.4.2.1.2"), -1),
            (OID(".1.3.6.1.4.2.1.3"),  1),
            (OID(".1.3.6.1.4.2.1.4"), "test value"),
            ]

    def setUpSession(self, address):
        self.session = Session(
                version=self.version,
                community="public",
                peername=address)
        self.session.open()

    def tearDownSession(self):
        self.session.close()

    def test_sget(self):
        result = self.session.sget([x for x,v in self.basics])
        self.assertEquals(result, self.basics)

    def test_get1(self):
        result = Result()
        self.session.get([x for x,v in self.basics], set_result, result)
        self.session.wait()
        self.assertEquals(result.value, self.basics)

    def test_get2(self):
        oids = []
        for i in xrange(1, 100):
            oids.append(OID((1,3,6,1,4,2,4,i)))

        result = Result()
        self.session.get(oids, set_result, result)
        self.session.wait()

        result = dict(result.value)
        for oid in oids:
            assert oid in result
            assert result[oid] == "data data data data"

    def test_walk1(self):
        result = Result()
        self.session.walk([".1.3.6.1.4.2.1"], set_result, result)
        self.session.wait()
        self.assertEquals(result.value, self.basics)

    def test_walk2(self):
        oid = OID(".1.3.6.1.4.2.1.1")
        result = Result()
        self.session.walk([oid], set_result, result)
        self.session.wait()
        self.assertEquals(result.value, [(oid, 1)])

class TestSessionV2c(TestSessionV1):

    version = "2c"

class TestTimeoutsV1(unittest.TestCase):

    version = "1"

    def setUp(self):
        self.session = Session(
                version=self.version,
                community="public",
                peername="udp:127.0.0.1:9",
                retries=0, timeout=0.1)
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

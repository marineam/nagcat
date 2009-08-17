from twisted.trial import unittest

from snapy import netsnmp
from snapy.netsnmp.unittests import TestCase

class Result(object):
    """Container for async results"""
    value = None

def set_result(value, result):
    result.value = value

class TestSessionV1(TestCase):

    version = "1"
    basics = {
            ".1.3.6.1.4.2.1.1": 1,
            ".1.3.6.1.4.2.1.2": -1,
            ".1.3.6.1.4.2.1.3": 1,
            ".1.3.6.1.4.2.1.4": "test value",
            }

    def test_sget(self):
        result = self.session.sget(self.basics.keys())
        self.assertEquals(result, self.basics)

    def test_get(self):
        result = Result()
        self.session.get(self.basics.keys(), set_result, result)
        self.session.wait()
        self.assertEquals(result.value, self.basics)

    def test_getnext_single(self):
        """Test a standard walk using just getnext"""

        all = {}
        oid = ".1.3.6.1.4.2.1"

        while oid:
            result = Result()
            self.session.getnext([oid], set_result, result)
            self.session.wait()

            oid = result.value.keys()[0]
            if result.value[oid]:
                all.update(result.value)
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

    def test_walk(self):
        result = Result()
        self.session.walk(".1.3.6.1.4.2.1", set_result, result)
        self.session.wait()
        self.assertEquals(result.value, self.basics)

class TestSessionV2c(TestSessionV1):

    version = "2c"


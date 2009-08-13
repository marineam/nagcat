from twisted.trial import unittest

from snapy import netsnmp
from snapy.netsnmp.unittests import TestCase

class TestSessionV1(TestCase):

    version = "1"

    def test_sget(self):
        expect = {
                ".1.3.6.1.4.2.1.0": 1,
                ".1.3.6.1.4.2.2.0": -1,
                ".1.3.6.1.4.2.3.0": 1,
                ".1.3.6.1.4.2.4.0": "test value",
                }
        result = self.session.sget(expect.keys())
        self.assertEquals(result, expect)

class TestSessionV2c(TestSessionV1):

    version = "2c"


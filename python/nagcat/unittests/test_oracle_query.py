#!/usr/bin/python

# Place a suitable copyright statement here...

"""Purpose of this file..
(a line or two of detail about what or why)"""
__revision__ = "$Id: 0 0 0 $"
__version__ = "%s/%s" % (__revision__.split()[3], __revision__.split()[2])

import os
from twisted.trial import unittest
from nagcat.unittests import dummy_server
from nagcat import errors, query
from coil.struct import Struct

# NOTE: user/pw/sid are not included here, for security reasons.  Please set the
# following environment variables accordingly when running this test:
# ORA_USER, ORA_PASS, ORA_DSN
class OracleTestCase(unittest.TestCase):
    def setUp(self):
        self.config = Struct({'user':os.environ['ORA_USER'],
                              'password':os.environ['ORA_PASS'],
                              'dsn':os.environ['ORA_DSN'],
                              'sql':'select 1 as data from dual'})

    def testSimple(self):
        q = query.Query_oraclesql(self.config)
        d = q.start()
        d.addBoth(self.endSimple, q)
        return d

    def endSimple(self, ignore, q):
        expected = '<queryresult><row><data type="NUMBER">1</data></row></queryresult>'
        self.assertEquals(q.result, expected)


# class OracleSQLErrorTestCase(unittest.TestCase):
#     def setUp(self):
#         self.config = Struct({'user':os.environ['ORA_USER'],
#                               'password':os.environ['ORA_PASS'],
#                               'dsn':os.environ['ORA_DSN'],
#                               'sql':'this is invalid sql'})
#     def testBadQuery(self):
#         q = query.Query_oraclesql(self.config)
#         d = q.start()
#         d.addBoth(self.endBadQuery, q)
#         return d
#     def endBadQuery(self, ignore, q):
#         self.assertIsInstance(q.result, errors.Failure)


class OracleBadLoginTestCase(unittest.TestCase):
    def setUp(self):
        self.config = Struct({'user':'baduser', 
                              'password':'pw', 
                              'dsn':'nodb',
                              'sql':'select 1 from dual'})

    def testBadQuery(self):
        q = query.Query_oraclesql(self.config)
        d = q.start()
        d.addBoth(self.endBadQuery, q)
        return d

    def endBadQuery(self, ignore, q):
        self.assertIsInstance(q.result, errors.Failure)


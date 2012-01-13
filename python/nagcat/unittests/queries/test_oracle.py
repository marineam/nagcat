# Copyright 2008-2009 ITA Software, Inc.
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

import os
import time
import subprocess

from twisted.internet import protocol, reactor
from twisted.python import log
from twisted.trial import unittest
from nagcat.plugins import query_oracle
from nagcat.unittests.queries import QueryTestCase
from nagcat import errors
from coil.struct import Struct

try:
    import cx_Oracle
    from lxml import etree
except ImportError:
    cx_Oracle = None
    etree = None

class OracleBase(QueryTestCase):
    if not cx_Oracle or not etree:
        skip = "Missing cx_Oracle or lxml"
    elif not ('ORA_DSN' in os.environ and
              'ORA_USER' in os.environ and
              'ORA_PASS' in os.environ):
        skip = "Missing oracle credentials"

    SQL_SETUP = ()
    SQL_CLEAN = ()

    QUERY_TYPE = "oracle_sql"

    def setUp(self):
        super(OracleBase, self).setUp()
        self.config = {
                'type': self.QUERY_TYPE,
                'user': os.environ['ORA_USER'],
                'password':os.environ['ORA_PASS'],
                'dsn':os.environ['ORA_DSN']}
        if self.SQL_SETUP:
            self.execute(self.SQL_SETUP)

    def tearDown(self):
        if self.SQL_CLEAN:
            self.execute(self.SQL_CLEAN)

    def execute(self, sqlseq):
        conn = cx_Oracle.Connection(user=self.config['user'],
                                    password=self.config['password'],
                                    dsn=self.config['dsn'],
                                    threaded=True)
        self.execute_in_connection(sqlseq, conn)
        conn.close()

    def execute_in_connection(self, sqlseq, conn):
        cursor = conn.cursor()
        for sql in sqlseq:
            try:
                cursor.execute(sql)
            except cx_Oracle.DatabaseError, ex:
                raise Exception("%s: %s" % (ex, sql))
        cursor.close()

    def startQuery(self, **kwargs):
        return super(OracleBase, self).startQuery(self.config, **kwargs)

    def assertEqualsXML(self, result, expect):
        # Parse the xml, strip white space, and convert back
        # this allows us to compare if they are logically equal
        parser = etree.XMLParser(remove_blank_text=True)
        result = etree.tostring(etree.XML(result, parser))
        expect = etree.tostring(etree.XML(expect, parser))
        self.assertEquals(result, expect)

class SimpleTestCase(OracleBase):

    def testSimple(self):
        def check(result):
            self.assertEqualsXML(result, (
                '<queryresult><row>'
                    '<data type="NUMBER">1</data>'
                '</row></queryresult>'))

        d = self.startQuery(sql='select 1 as data from dual')
        d.addCallback(check)
        return d

    def testBinds(self):
        def check(result):
            self.assertEqualsXML(result, (
                '<queryresult><row>'
                    '<data type="NUMBER">1</data>'
                '</row></queryresult>'))

        d = self.startQuery(
                sql='select :blah as data from dual',
                binds=[1])
        d.addCallback(check)
        return d

    def testParams1(self):
        def check(result):
            self.assertEqualsXML(result, (
                '<queryresult><row>'
                    '<data type="NUMBER">2</data>'
                '</row></queryresult>'))

        d = self.startQuery(
                sql='select :blah as data from dual',
                parameters=[2])
        d.addCallback(check)
        return d

    def testParams2(self):
        def check(result):
            self.assertEqualsXML(result, (
                '<queryresult><row>'
                    '<data type="NUMBER">2</data>'
                '</row></queryresult>'))

        d = self.startQuery(
                sql='select :blah as data from dual',
                parameters=Struct({'blah': 2}))
        d.addCallback(check)
        return d

    def testString(self):
        def check(result):
            self.assertEqualsXML(result, (
                '<queryresult><row>'
                    '<data type="FIXED_CHAR">foo</data>'
                '</row></queryresult>'))

        d = self.startQuery(sql="select 'foo' as data from dual")
        d.addCallback(check)
        return d

    def testBadQuery(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
        d = self.startQuery(sql='select 1')
        d.addBoth(check)
        return d

    def testBadUser(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
        d = self.startQuery(sql='select 1 from dual', user='baduser')
        d.addBoth(check)
        return d

class DataTestCase(OracleBase):

    SQL_SETUP = (
        "create table test (a number, b varchar2(10))",
        "insert into test values (1, 'aaa')",
        "insert into test values (2, 'bbb')",
        "insert into test values (3, 'ccc')",
        "insert into test values (4, 'ddd')",
        "insert into test values (5, 'eee')",
        "commit")

    SQL_CLEAN = ("drop table test", "commit")

    def testSelectAll(self):
        def check(result):
            self.assertEqualsXML(result, """<queryresult>
                <row><a type="NUMBER">1</a><b type="STRING">aaa</b></row>
                <row><a type="NUMBER">2</a><b type="STRING">bbb</b></row>
                <row><a type="NUMBER">3</a><b type="STRING">ccc</b></row>
                <row><a type="NUMBER">4</a><b type="STRING">ddd</b></row>
                <row><a type="NUMBER">5</a><b type="STRING">eee</b></row>
            </queryresult>""")

        d = self.startQuery(sql='select * from test')
        d.addCallback(check)
        return d

    def testSelectCount(self):
        def check(result):
            self.assertEqualsXML(result, """<queryresult>
                <row><count type="NUMBER">5</count></row>
            </queryresult>""")

        d = self.startQuery(sql='select count(*) from test')
        d.addCallback(check)
        return d

    def testNonSelect(self):
        # The result should be empty if we didn't actually select data
        def check(result):
            self.assertEqualsXML(result, "<queryresult></queryresult>")

        d = self.startQuery(sql="insert into test values (0, 'xxx')")
        d.addCallback(check)
        return d


class TimeoutQueryTestCase(OracleBase):

    SQL_SETUP = ("create table test (a number)", "commit")
    SQL_CLEAN = ("drop table test", "commit")

    def setUp(self):
        super(TimeoutQueryTestCase, self).setUp()

        self.locked_conn = cx_Oracle.Connection(
                user=self.config['user'],
                password=self.config['password'],
                dsn=self.config['dsn'],
                threaded=True)
        self.execute_in_connection((
                "lock table test in exclusive mode",
                ), self.locked_conn)

    def tearDown(self):
        self.locked_conn.close()
        self.locked_conn = None
        super(TimeoutQueryTestCase, self).tearDown()

    def test_timeout(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assert_(str(result.value).startswith("Timeout"),
                    "Wrong error, got: %s" % result.value)

        deferred = self.startQuery(
                sql='lock table test in exclusive mode',
                timeout=0.5)
        deferred.addBoth(check)
        return deferred


class DummyFactory(protocol.Factory):
    protocol = protocol.Protocol

class TimeoutConnectionTestCase(QueryTestCase):
    """Test killing hanging TCP connections"""

    if not cx_Oracle or not etree:
        skip = "Missing cx_Oracle"

    def setUp(self):
        super(TimeoutConnectionTestCase, self).setUp()
        # I assume this test isn't going to be run on an Oracle server...
        self.server = reactor.listenTCP(1521, DummyFactory())
        self.config = {
                'type': 'oracle_sql',
                'user': 'nobody',
                'password': 'ponies',
                'timeout': 0.5,
                'dsn': 'localhost/blackhole'}

    def tearDown(self):
        return self.server.stopListening()

    def test_timeout(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assert_(str(result.value).startswith("Timeout"),
                    "Wrong error, got: %s" % result.value)

        d = self.startQuery(self.config)
        d.addBoth(check)
        return d


class PLSQLTestCase(OracleBase):

    SQL_CLEAN = ("drop package pltest", "commit")

    QUERY_TYPE = "oracle_plsql"

    def setUp(self):
        super(PLSQLTestCase, self).setUp()
        path = "%s/%s" % (os.path.dirname(os.path.abspath(__file__)),
                          "oracle_package.sql")

        # For some reason running this SQL via cx_Oracle doesn't
        # work, but it does with sqlplus. I don't know why. :-(
        input = open(path)
        proc = subprocess.Popen(
            ["sqlplus", "-S", "-L", "%s/%s@%s" % (
                self.config['user'],
                self.config['password'],
                self.config['dsn'])],
            stdin=input,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        input.close()
        out,bleh = proc.communicate()
        for line in out.splitlines():
            line = line.strip()
            if line:
                log.msg("[sqlplus] %s" % line)

        assert proc.returncode == 0

    def test_1(self):
        def check(result):
            self.assertEqualsXML(result,
            """<result>
                <p_out type="NUMBER">1.0</p_out>
            </result>""")

        d = self.startQuery(procedure="pltest.one",
                parameters=[['out', 'p_out', "number"]])
        d.addCallback(check)
        return d

    def test_2(self):
        def check(result):
            self.assertEqualsXML(result,
            """<result>
                <p_out type="NUMBER">3.0</p_out>
            </result>""")

        d = self.startQuery(procedure="pltest.two",
                parameters=[['in', 'p_in', 7],
                    ['out', 'p_out', 'number']])
        d.addCallback(check)
        return d

    def test_3(self):
        def check(result):
            self.assertEqualsXML(result,
            """<result>
                <p_out>
                    <row><level type="NUMBER">1</level></row>
                    <row><level type="NUMBER">2</level></row>
                    <row><level type="NUMBER">3</level></row>
                    <row><level type="NUMBER">4</level></row>
                    <row><level type="NUMBER">5</level></row>
                    <row><level type="NUMBER">6</level></row>
                    <row><level type="NUMBER">7</level></row>
                    <row><level type="NUMBER">8</level></row>
                    <row><level type="NUMBER">9</level></row>
                    <row><level type="NUMBER">10</level></row>
                </p_out>
            </result>""")

        d = self.startQuery(procedure="pltest.three",
                parameters=[['out', 'p_out', 'cursor']])
        d.addCallback(check)
        return d

    def test_4(self):
        def check(result):
            self.assertEqualsXML(result,
            """<result>
                <p_one>
                    <row><level type="NUMBER">1</level></row>
                    <row><level type="NUMBER">2</level></row>
                    <row><level type="NUMBER">3</level></row>
                    <row><level type="NUMBER">4</level></row>
                    <row><level type="NUMBER">5</level></row>
                    <row><level type="NUMBER">6</level></row>
                    <row><level type="NUMBER">7</level></row>
                    <row><level type="NUMBER">8</level></row>
                    <row><level type="NUMBER">9</level></row>
                    <row><level type="NUMBER">10</level></row>
                </p_one>
                <p_two>
                    <row><level type="NUMBER">1</level></row>
                    <row><level type="NUMBER">2</level></row>
                    <row><level type="NUMBER">3</level></row>
                    <row><level type="NUMBER">4</level></row>
                    <row><level type="NUMBER">5</level></row>
                    <row><level type="NUMBER">6</level></row>
                    <row><level type="NUMBER">7</level></row>
                    <row><level type="NUMBER">8</level></row>
                    <row><level type="NUMBER">9</level></row>
                    <row><level type="NUMBER">10</level></row>
                </p_two>
            </result>""")

        d = self.startQuery(procedure="pltest.four",
                parameters=[['out', 'p_one', 'cursor'],
                            ['out', 'p_two', 'cursor']])
        d.addCallback(check)
        return d

    def test_5(self):
        def check(result):
            # The current behavior of the conversion to XML is to
            # represent NULL as an empty element. But what about
            # NULL vs empty strings? Do we care?
            self.assertEqualsXML(result,
            """<result>
                <p_one type="NUMBER">1.0</p_one>
                <p_two type="NUMBER"/>
            </result>""")

        d = self.startQuery(procedure="pltest.five",
                parameters=[['out', 'p_one', 'number'],
                            ['out', 'p_two', 'number']])
        d.addCallback(check)
        return d

class ForkItTestCase(unittest.TestCase):
    """Test my defer-to-subprocess type class"""

    def testNone(self):
        proc = query_oracle.ForkIt(1, lambda: None)
        d = proc.getResult()
        d.addBoth(self.assertIdentical, None)
        return d

    def testTrue(self):
        proc = query_oracle.ForkIt(1, lambda: True)
        d = proc.getResult()
        d.addBoth(self.assertIdentical, True)
        return d

    def testAbort(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestUnknown)
            self.assertIn("subprocess exited with no results",
                          str(result.value))
        proc = query_oracle.ForkIt(1, os._exit, 0)
        d = proc.getResult()
        d.addBoth(check)
        return d

    testAbort.skip = "Flaky test :-/"

    def testTimeout(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)
            self.assertIn("Timeout", str(result.value))
        proc = query_oracle.ForkIt(0.1, time.sleep, 10)
        d = proc.getResult()
        d.addBoth(check)
        return d

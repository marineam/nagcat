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

from snapy.netsnmp import OID
from snapy.netsnmp.unittests import TestCase
from snapy.twisted import Session

class TestSessionV1(TestCase):

    version = "1"

    def setUpSession(self, address):
        self.session = Session(
                version=self.version,
                community="public",
                peername=address)
        self.session.open()

    def tearDownSession(self):
        self.session.close()

    def test_get(self):
        oid = OID(".1.3.6.1.4.2.1.1")
        def cb(result):
            self.assertEquals(result, [(oid, 1)])

        d = self.session.get([oid])
        d.addCallback(cb)
        return d

    def test_walk(self):
        root = OID('.1.3.6.1.4.2.3')
        expect = [(root + OID([i]), i) for i in xrange(1,5)]

        def cb(result):
            self.assertEquals(result, expect)

        d = self.session.walk([root])
        d.addCallback(cb)
        return d

class TestSessionV2c(TestSessionV1):

    version = "2c"


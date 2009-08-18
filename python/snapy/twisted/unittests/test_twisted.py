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

from snapy.netsnmp.unittests import TestCase
from snapy.twisted import Session

class TestSessionV1(TestCase):

    version = "1"

    def setUp2(self):
        self.session = Session("-v", self.version, "-c", "public",
                "127.0.0.1:%d" % self.server.port)
        self.session.open()

    def tearDown2(self):
        self.session.close()

    def test_get(self):
        def cb(result):
            self.assertEquals(result, {".1.3.6.1.4.2.1.1": 1})

        d = self.session.get([".1.3.6.1.4.2.1.1"])
        d.addCallback(cb)
        return d

class TestSessionV2c(TestSessionV1):

    version = "2c"


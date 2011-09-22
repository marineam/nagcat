# Copyright 2011 Google, Inc.
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
from nagcat import merlin
from coil.struct import Struct
import os
import MySQLdb


class TestNagcatMerlinCase(unittest.TestCase):

    def setUp(self):
        try:
            self._merlin_db_info = {
                "merlin_db_user": os.environ['MYSQL_USER'],
                "merlin_db_host": os.environ['MYSQL_HOST'],
                "merlin_db_pass": os.environ['MYSQL_PASS'],
                "merlin_db_name": os.environ['MYSQL_NAME'],
                #"merlin_db_port": os.environ['MYSQL_PORT'],
            }
        except KeyError, e:
            self.fail("Key error: %s" % e)
        try:
            db = MySQLdb.connect(
                user=self._merlin_db_info['merlin_db_user'],
                host=self._merlin_db_info['merlin_db_host'],
                passwd=self._merlin_db_info['merlin_db_pass'],
                db=self._merlin_db_info['merlin_db_name'])

            cursor = db.cursor()
            cursor.execute("""drop table if exists merlin_peers;""")
            cursor.execute("""create table merlin_peers(
                    name    varchar(70) NOT NULL PRIMARY KEY,
                    id      int(22),
                    sock    int(22),
                    type    int(1) NOT NULL,
                    state   int(22) NOT NULL,
                    peer_id int(22) NOT NULL);""")
            cursor.execute("""insert into merlin_peers values(
                    'localhost',
                    '1',
                    '1',
                    '1',
                    '3',
                    '0');""")
            cursor.execute("""insert into merlin_peers values(
                    'otherhost',
                    '1',
                    '1',
                    '1',
                    '3',
                    '1');""")
        except MySQLdb.Error, e:
            self.fail("Could not connect to database %d: %s" % (e.args[0],
                e.args[1]))

    def testNagcatMerlin(self):
        nagcatMerlin = merlin.NagcatMerlinDummy(merlin_db_info=self._merlin_db_info)
        self.assertEquals(nagcatMerlin.get_peer_id_num_peers(),
        (0,2))

    def tearDown(self):
        try:
            db = MySQLdb.connect(
                user = self._merlin_db_info['merlin_db_user'],
                host = self._merlin_db_info['merlin_db_host'],
                passwd = self._merlin_db_info['merlin_db_pass'],
                db = self._merlin_db_info['merlin_db_name'])
            curs = db.cursor()
            curs.execute("""DROP table merlin_peers;""")
        except MySQLdb.Error, e:
            self.fail("Could not clean up database %d: %s" % (e.args[0],
                e.args[1]))


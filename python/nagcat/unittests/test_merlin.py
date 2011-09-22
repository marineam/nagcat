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
from nagcat import simple, merlin, scheduler
from coil.struct import Struct
import os
import warnings
import MySQLdb

class TestNagcatMerlinCase(unittest.TestCase):

    def setUp(self):
        self._merlin_db_info = {
            "merlin_db_user": os.environ.get('MYSQL_USER', None),
            "merlin_db_host": os.environ.get('MYSQL_HOST', None),
            "merlin_db_pass": os.environ.get('MYSQL_PASS', None),
            "merlin_db_name": os.environ.get('MYSQL_NAME', None),
            "merlin_db_port": os.environ.get('MYSQL_PORT', 3306),
        }
        self._should_skip = not all([self._merlin_db_info['merlin_db_user'],
            self._merlin_db_info['merlin_db_host'],
            self._merlin_db_info['merlin_db_name']])
        if self._should_skip:
            raise unittest.SkipTest("Not enough database information")
        db = MySQLdb.connect(
            user=self._merlin_db_info['merlin_db_user'],
            host=self._merlin_db_info['merlin_db_host'],
            passwd=self._merlin_db_info['merlin_db_pass'],
            db=self._merlin_db_info['merlin_db_name'])

        cursor = db.cursor()
        # drop table raises a warning if the table doesn't exist, so shutup!
        warnings.filterwarnings('ignore', 'Unknown table.*')
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

    def testNagcatMerlin(self):
        nagcatMerlin = NagcatMerlinDummy(
            merlin_db_info=self._merlin_db_info)
        self.assertEquals(nagcatMerlin.get_peer_id_num_peers(),
            (0,2))

    def tearDown(self):
        db = MySQLdb.connect(
            user = self._merlin_db_info['merlin_db_user'],
            host = self._merlin_db_info['merlin_db_host'],
            passwd = self._merlin_db_info['merlin_db_pass'],
            db = self._merlin_db_info['merlin_db_name'])
        curs = db.cursor()
        curs.execute("""DROP table merlin_peers;""")

class NagcatMerlinDummy(merlin.NagcatMerlin):
    """For testing purposes."""
    def __init__(self, merlin_db_info={}):
        self._merlin_db_info = merlin_db_info
        scheduler.Scheduler.__init__(self)
        self._peer_id = None
        self._num_rows = None
        self._peer_id_timestamp = None

    def build_tests(self, config):
        return []

    def nagios_status(self):
        return simple.ObjectDummy()

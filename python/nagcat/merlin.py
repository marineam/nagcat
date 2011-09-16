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
import errno
import MySQLdb
import time

from coil.errors import CoilError
from nagcat import errors, log, nagios_api, nagios_objects, scheduler, merlintest,nagios

class NagcatMerlin(nagios.NagcatNagios):
    """NagcatNagios scheduler that load balances using merlin."""

    def __init__(self, config, nagios_cfg, merlin_db_info={}, **kwargs):

        self._test_index = 0
        self._merlin_db_info = merlin_db_info
        return super(NagcatMerlin, self).__init__(config, nagios_cfg, **kwargs)



    def new_test(self, config):
        new = merlintest.MerlinTest(self, config, self._test_index)
        self._test_index += 1
        self.register(new)
        if self.trend:
            self.trend.setup_test_trending(new, config)
        return new

    def _set_peer_id_and_timestamp(self):
        """ Gets a peer_id and sets a timestamp for when it acquired the peer_id
        The peer_id comes from merlin, and is obtained by reading a database,
        which Merlin outputs data to."""
        try:
            db = MySQLdb.connect(
                user=self._merlin_db_info['merlin_db_user'],
                host=self._merlin_db_info['merlin_db_host'],
                passwd=self._merlin_db_info['merlin_db_pass'],
                db=self._merlin_db_info['merlin_db_name'])
            curs = db.cursor()
            num_rows = curs.execute(
                """select * from merlin_peers where state=3;""")
            self._num_peers = num_rows
            log.debug("Seeting self._num_peers = %s", num_rows)
            for i in range(num_rows):
                row = curs.fetchone()
                if row[0] == "localhost":
                    self._peer_id = row[5]
                    self._peer_id_timestamp = time.time()
                    log.debug(("Setting self._peer_id = %s", str(self._peer_id)) +
                        ("and self._peer_id_timestamp = %s",
                        self._peer_id_timestamp))
        except MySQLdb.Error, e:
            log.error("Error %d: %s" % (e.args[0], e.args[1]))

    def _update_peer_id(self):
        log.debug("Updating peer_id with _merlin_db_info=%s",
            self._merlin_db_info)
        if self._peer_id and self._peer_id_timestamp:
            if time.time() - self._peer_id_timestamp >= 60:
                # peer_id should be refreshed.
                self._set_peer_id_and_timestamp()
            else:
                # peer_id is still valid, return.
                return
        else: # We are missing peer_id or peer_id_timestamp...
            if self._merlin_db_info:
                self._set_peer_id_and_timestamp()

    def get_peer_id(self):
        self._update_peer_id()
        return self._peer_id

    def get_num_peers(self):
        self._update_peer_id()
        return self._num_peers



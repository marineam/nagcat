# Copyright 2009 ITA Software, Inc.
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
from nagcat.unittests.queries import QueryTestCase
from nagcat import errors, query, plugin
from coil.struct import Struct


class NTPTestCase(QueryTestCase):

    if 'NTP_HOST' in os.environ:
        ntp_host = os.environ['NTP_HOST']
    else:
        skip = "Set NTP_HOST to run NTP unit tests."

    def testSimple(self):
        conf = Struct({'type': 'ntp',
                'host': self.ntp_host,
                'port': 123})
        now = time.time()
        qcls = plugin.search(query.IQuery, 'ntp')
        q = qcls(self.nagcat, conf)

        def check(ignore):
            # chop off a bunch of time because they won't be exact
            self.assertEquals(time.time() // 3600,
                    int(q.result) // 3600)

        d = q.start()
        d.addCallback(check)
        return d

    def testRefused(self):
        conf = Struct({'type': 'ntp',
                'host': 'localhost',
                'port': 9,
                'timeout': 2})
        now = time.time()
        qcls = plugin.search(query.IQuery, 'ntp')
        q = qcls(self.nagcat, conf)

        def check(ignore):
            self.assertIsInstance(q.result, errors.Failure)
            self.assertIsInstance(q.result.value, errors.TestCritical)

        d = q.start()
        d.addCallback(check)
        return d

    # TODO: test timeout

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
from nagcat import errors


class NTPTestCase(QueryTestCase):

    if 'NTP_HOST' in os.environ:
        ntp_host = os.environ['NTP_HOST']
    else:
        skip = "Set NTP_HOST to run NTP unit tests."

    def testSimple(self):
        def check(result):
            # chop off a bunch of time because they won't be exact
            self.assertEquals(time.time() // 3600,
                    int(result) // 3600)

        d = self.startQuery(type="ntp", host=self.ntp_host, port=123)
        d.addCallback(check)
        return d

    def testRefused(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)

        d = self.startQuery(type="ntp", host='localhost', port=9)
        d.addBoth(check)
        return d

    # TODO: test timeout

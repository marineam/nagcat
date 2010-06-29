# Copyright 2010 ITA Software, Inc.
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
from nagcat import errors, simple, trend
from coil.struct import Struct

try:
    from lxml import etree
except ImportError:
    etree = None

class LastUpdateTestCase(QueryTestCase):

    if not trend.rrdtool or not etree:
        skip = "missing rrdtool or lxml"

    def setUp(self):
        rradir = self.mktemp()
        os.mkdir(rradir)
        self.nagcat = simple.NagcatDummy(rradir=rradir)

        self.config = {
                'type': 'rrd_lastupdate',
                'host': 'testhost',
                'addr': None,
                'description': 'testservice',
            }

        source_config = Struct({
                'query': {
                    'type': 'compound',
                    'one': {
                        'type': 'noop',
                        'data': '1',
                        'trend': { 'type': 'gauge' },
                    },
                    'two': {
                        'type': 'noop',
                        'data': '2',
                        'trend': { 'type': 'gauge' },
                    },
                    'return': "$(one) + $(two)",
                },
                'trend': { 'type': 'gauge' },
                'host': self.config['host'],
                'addr': None,
                'description': self.config['description'],
            })
        source_test = self.nagcat.new_test(source_config)
        return source_test.start()

    def testFullData(self):
        def check(result):
            tree = etree.fromstring(result)
            self.assertEquals(
                    tree.xpath('/rrd/ds[name/text() = "one"]/last_ds/text()'),
                    ['1.0'])
            self.assertEquals(
                    tree.xpath('/rrd/ds[name/text() = "two"]/last_ds/text()'),
                    ['2.0'])
            self.assertEquals(
                    tree.xpath('/rrd/ds[name/text() = "_result"]/last_ds/text()'),
                    ['3.0'])
            self.assertEquals(
                    tree.xpath('/rrd/ds[name/text() = "_state"]/last_ds/text()'),
                    ['0.0'])

        d = self.startQuery(self.config)
        d.addCallback(check)
        return d

    def testSingleData(self):
        d = self.startQuery(self.config, source='two')
        d.addCallback(self.assertEquals, '2.0')
        return d

    def testTime(self):
        def check(result):
            tree = etree.fromstring(result)
            now = time.time()
            then = int(tree.xpath('/rrd/lastupdate/text()')[0])
            self.assertApproximates(then, now, 2)

        d = self.startQuery(self.config)
        d.addCallback(check)
        return d

    def testFreshness(self):
        def check(result):
            self.assertIsInstance(result, errors.Failure)
            self.assertIsInstance(result.value, errors.TestCritical)

        d = self.startQuery(self.config, freshness=-2)
        d.addBoth(check)
        return d

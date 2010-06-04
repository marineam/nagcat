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
from glob import glob
from twisted.trial import unittest
from coil.struct import Struct
from nagcat import trend

if trend.rrdtool:
    import twirrdy

class TrendDataTestCase(unittest.TestCase):

    if trend.rrdtool is None:
        skip = "rrdtool is not installed"

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)

    def testSingle(self):
        conf = Struct({'type': "gauge",
                       'host': "testhost",
                       'name': "single",
                       'repeat': "5m",
                       'trend': {'type': "gauge"},
                       'query': {'type': "dummy"}})

        data = open(os.path.join(os.path.dirname(__file__), "trend_data1"))
        start_time, value = data.readline().split()
        start_time = int(start_time)

        trendobj = trend.Trend(conf, self.tmpdir, start_time-10)
        report = {'state_id': 0, 'time': start_time, 'output': value }
        trendobj.update(report)

        for line in data:
            end_time, value = line.split()
            end_time = int(end_time)
            report['time'] = end_time
            report['output'] = value
            trendobj.update(report)

        data.close()

    def testMultiple(self):
        conf = Struct({
            'host': "testhost",
            'name': "multiple",
            'repeat': "5m",
            'trend': {'type': "gauge"},
            'query': {
                'type': "compound",
                'data1': {
                    'type': "dummy",
                    'trend': {'type': "gauge"},
                },
                'data2': {
                    'type': "dummy",
                    'trend': {'type': "gauge"},
                },
            },
        })

        data1 = open(os.path.join(os.path.dirname(__file__), "trend_data1"))
        data2 = open(os.path.join(os.path.dirname(__file__), "trend_data2"))
        start_time1, value1 = data1.readline().split()
        start_time2, value2 = data2.readline().split()
        assert start_time1 == start_time2
        start_time = int(start_time1)

        trendobj = trend.Trend(conf, self.tmpdir, start_time-10)
        report = {'state_id': 0, 'time': start_time, 'output': "",
            'results': {'data1': value1, 'data2': value2} }
        trendobj.update(report)

        for line1, line2 in zip(data1, data2):
            end_time1, value1 = line1.split()
            end_time2, value2 = line2.split()
            assert end_time1 == end_time2
            report['time'] = int(end_time1)
            report['results']['data1'] = value1
            report['results']['data2'] = value2
            trendobj.update(report)

        data1.close()
        data2.close()

class TrendDataTestCase(unittest.TestCase):

    if trend.rrdtool is None:
        skip = "rrdtool is not installed"

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)

        self.conf = Struct({
            'host': "testhost",
            'name': "change",
            'repeat': "5m",
            'query': {
                'type': "compound",
                'data1': {
                    'type': "dummy",
                },
                'data2': {
                    'type': "dummy",
                },
            },
        })

        self.assertRRDCount(0)

    def assertRRDCount(self, count):
        rrd_glob = "%s/testhost/change.rrd*" % self.tmpdir
        self.assertEquals(len(glob(rrd_glob)), count)

    def testCreate(self):
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

    def testSingleAdd(self):
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        self.conf['trend.type'] = "gauge"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(2)

    def testSingleDel(self):
        self.conf['trend.type'] = "gauge"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        del self.conf['trend']
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(2)

    def testSingleChange(self):
        self.conf['trend.type'] = "gauge"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        self.conf['trend.type'] = "counter"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(2)

    def testSubQueryAdd1(self):
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        self.conf['query.data1.trend.type'] = "gauge"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(2)

    def testSubQueryAdd2(self):
        self.conf['query.data1.trend.type'] = "gauge"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        self.conf['query.data2.trend.type'] = "gauge"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(2)

    def testSubQueryDel(self):
        self.conf['query.data1.trend.type'] = "gauge"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        del self.conf['query.data1.trend']
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(2)

    def testSubQueryChange(self):
        self.conf['query.data1.trend.type'] = "gauge"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        self.conf['query.data1.trend.type'] = "counter"
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(2)

class TrendRRATestCase(unittest.TestCase):

    if trend.rrdtool is None:
        skip = "rrdtool is not installed"

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)

        self.conf = Struct({
            'host': "testhost",
            'name': "rratest",
            'repeat': "1m",
            'query': {'type': "noop"},
            'trend': {'type': "gauge"},
        })
        self.assertRRDCount(0)

    def rrdtool_info(self):
        rrd_path = "%s/testhost/rratest.rrd" % self.tmpdir
        api = twirrdy.RRDBasicAPI()
        return api.info(rrd_path)

    def assertRRDCount(self, count):
        rrd_glob = "%s/testhost/rratest.rrd*" % self.tmpdir
        self.assertEquals(len(glob(rrd_glob)), count)

    def assertRRA(self, rra, cf, steps, rows):
        self.assertEquals(rra['cf'], cf)
        self.assertEquals(rra['pdp_per_row'], steps)
        self.assertEquals(rra['rows'], rows)
        self.assertEquals(rra['xff'], 0.5)

    def testDefaults(self):
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)
        rra = self.rrdtool_info()['rra']
        # Should be 2 cf per 5 default intervals
        self.assertEquals(len(rra), 10)

        # 1 minute intervals for 2 days
        self.assertRRA(rra[0], 'MAX',     1, 2880)
        self.assertRRA(rra[1], 'AVERAGE', 1, 2880)

        # 5 minute intervals for 2 weeks
        self.assertRRA(rra[2], 'MAX',     5, 4032)
        self.assertRRA(rra[3], 'AVERAGE', 5, 4032)

        # 30 minute intervals for 2 months
        self.assertRRA(rra[4], 'MAX',     30, 2976)
        self.assertRRA(rra[5], 'AVERAGE', 30, 2976)

        # 2 hour intervals for 1 year
        self.assertRRA(rra[6], 'MAX',     120, 4392)
        self.assertRRA(rra[7], 'AVERAGE', 120, 4392)

        # 1 day intervals for 6 years
        self.assertRRA(rra[8], 'MAX',     1440, 2196)
        self.assertRRA(rra[9], 'AVERAGE', 1440, 2196)

    def testGrow(self):
        self.conf['trend.rra._60'] = 1440
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        rra = self.rrdtool_info()['rra']
        self.assertEquals(len(rra), 10)
        self.assertRRA(rra[0], 'MAX',     1, 24)
        self.assertRRA(rra[1], 'AVERAGE', 1, 24)

        self.conf['trend.rra._60'] = 14400
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        rra = self.rrdtool_info()['rra']
        self.assertEquals(len(rra), 10)
        self.assertRRA(rra[0], 'MAX',     1, 240)
        self.assertRRA(rra[1], 'AVERAGE', 1, 240)

    def testShrink(self):
        self.conf['trend.rra._60'] = 14400
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        rra = self.rrdtool_info()['rra']
        self.assertEquals(len(rra), 10)
        self.assertRRA(rra[0], 'MAX',     1, 240)
        self.assertRRA(rra[1], 'AVERAGE', 1, 240)

        self.conf['trend.rra._60'] = 1440
        trend.Trend(self.conf, self.tmpdir)
        self.assertRRDCount(1)

        rra = self.rrdtool_info()['rra']
        self.assertEquals(len(rra), 10)
        self.assertRRA(rra[0], 'MAX',     1, 24)
        self.assertRRA(rra[1], 'AVERAGE', 1, 24)

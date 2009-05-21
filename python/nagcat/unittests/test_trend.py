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
import rrdtool
from twisted.trial import unittest
from coil.struct import Struct
from nagcat import trend

class TrendData1TestCase(unittest.TestCase):
    dataset = "trend_data1"

    def setUp(self):
        self.conf = Struct({'type': "gauge",
                       'host': "testhost",
                       'name': self.dataset,
                       'repeat': "5m",
                       'trend': {'type': "gauge"},
                       'query': {'type': "dummy"}})
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        self.data = open(os.path.join(os.path.dirname(__file__), self.dataset))

    def testAll(self):
        start_time, value = self.data.readline().split()
        start_time = int(start_time)

        trendobj = trend.Trend(self.conf, self.tmpdir, start_time-10)
        report = {'state_id': 0, 'time': start_time, 'output': value }
        trendobj.update(report)

        for line in self.data:
            end_time, value = line.split()
            end_time = int(end_time)
            report['time'] = end_time
            report['output'] = value
            trendobj.update(report)

        graph_start = ((end_time - start_time) / 2) + start_time
        rrdtool.graph(os.path.join(self.tmpdir, "%s.png" % self.dataset),
                "--start", str(graph_start), "--end", str(end_time),
                "--width", "900", "--height", "400",
                "DEF:result=%s:_result:AVERAGE" % trendobj._rrafile,
                "DEF:state=%s:_state:AVERAGE" % trendobj._rrafile,
                "TICK:state#ffffa0:1.0:Failures",
                "LINE1:result#0000ff:Average Value")

    def tearDown(self):
        self.data.close()

class TrendData2TestCase(TrendData1TestCase):
    dataset = "trend_data2"

class TrendDiskTestCase(TrendData1TestCase):
    dataset = "trend_disk"

    def setUp(self):
        TrendData1TestCase.setUp(self)
        self.conf['type'] = "derive"

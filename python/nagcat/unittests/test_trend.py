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
                       'repeat': 300})
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        self.data = open(os.path.join(os.path.dirname(__file__), self.dataset))

    def testAll(self):
        start_time, value = self.data.readline().split()
        start_time = int(start_time)

        trendobj = trend._Trend(self.conf, self.tmpdir, start_time-10)
        trendobj.update(start_time, value)

        for line in self.data:
            end_time, value = line.split()
            end_time = int(end_time)
            trendobj.update(end_time, value)

        graph_start = ((end_time - start_time) / 2) + start_time
        rrdtool.graph(os.path.join(self.tmpdir, "%s.png" % self.dataset),
                "--start", str(graph_start), "--end", str(end_time),
                "--width", "900", "--height", "400",
                "DEF:obs=%s:default:AVERAGE" % trendobj.rrdfile,
                "DEF:pred=%s:default:HWPREDICT" % trendobj.rrdfile,
                "DEF:dev=%s:default:DEVPREDICT" % trendobj.rrdfile,
                "DEF:fail=%s:default:FAILURES" % trendobj.rrdfile,
                "TICK:fail#ffffa0:1.0:Failures",
                "CDEF:upper=pred,dev,2,*,+",
                "CDEF:lower=pred,dev,2,*,-",
                "LINE2:obs#0000ff:Average Value",
                "LINE1:upper#ff0000:Upper Confidence Bound",
                "LINE1:lower#ff0000:Lower Confidence Bound")

    def tearDown(self):
        self.data.close()

class TrendData2TestCase(TrendData1TestCase):
    dataset = "trend_data2"

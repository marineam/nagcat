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

"""RRDTool Trending"""

import os
import re

from twisted.python import logfile
import rrdtool

from nagcat import log, util

_rradir = None

def init(dir):
    global _rradir
    assert dir

    if not os.path.isdir(dir):
        raise util.InitError("%s is not a directory!" % repr(dir))

    if not os.access(dir, os.R_OK | os.W_OK | os.X_OK):
        raise util.InitError("%s is not readable and/or writeable!" % repr(dir))

    _rradir = dir

def Trend(config):
    """Generator for Trend objects, will return either a trending
    object or None depending on if trending is enabled.
    """

    if _rradir:
        return _Trend(config, _rradir)
    else:
        return None

class _Trend(object):

    #: Valid rrdtool data source types
    TYPES = ("GAUGE", "COUNTER", "DERIVE", "ABSOLUTE")

    #: RRAs required for graphing, (period, interval) in seconds
    RRAS = ((1440, 60),         # 4 hours of 1 minute intervals
            (86400, 300),       # 1 day of 5 minute intervals
            (604800, 1800),     # 7 days of 30 minute intervals
            (2678400, 7200),    # 31 days of 2 hour intervals
            (31622400, 86400))  # 366 days of 1 day intervals

    def __init__(self, config, dirname, start=None):
        self.conf = config
        self.conf.expand()
        self.type = self.conf.get('type', "").upper()
        self.step = int(self.conf.get('repeat'))
        self.alerts = bool(self.conf.get('alerts', False))
        self.season = int(util.Interval(self.conf.get('season', '1d')))
        self.alpha = float(self.conf.get('alpha', 0.001))
        self.beta = float(self.conf.get('beta', 0.0001))
        self.gamma = float(self.conf.get('gamma', 0.2))
        self.start = start

        self.dirname = dirname
        self.basename = "%s-%s" % (
                re.sub("[^a-z0-9_\.]", "", self.conf['host'].lower()),
                re.sub("[^a-z0-9_\.]", "", self.conf['name'].lower()))
        self.rrdfile = os.path.join(self.dirname, "%s.rrd" % self.basename)
        self.logfile = logfile.LogFile("%s.log" % self.basename, self.dirname,
                rotateLength=1024*1024, maxRotatedFiles=2)

        # Default to a 1 minute step when repeat is useless
        if self.step == 0:
            self.step = 60

        if self.type not in self.TYPES:
            raise util.KnownError("Invalid data source type: %s" % self.type)

        if os.path.exists(self.rrdfile):
            self.validate()
        else:
            self.create()

    def create(self):
        # For now just create archives with the minimal data required
        # to generate cacti graphs since that's where the data will be
        # displayed. More options can be added later...
        log.info("Creating RRA: %s" % self.rrdfile)

        args = ["--step", str(self.step)]

        if self.start:
            args += ["--start", str(self.start)]

        # Don't allow more than 1 missed update
        # TODO: support more than one data source
        args.append("DS:default:%s:%d:U:U" % (self.type, self.step*2))

        for period, interval in self.RRAS:
            if interval < self.step:
                continue
            steps = interval // self.step
            rows = period // steps
            args.append("RRA:MAX:0.5:%d:%d" % (steps, rows))
            args.append("RRA:AVERAGE:0.5:%d:%d" % (steps, rows))

        # The seasonal period is defined in terms of data points.
        # Save 5 seasons of data for now, not sure what the best value is...
        season_rows = self.season // self.step
        record_rows = season_rows * 5
        args.append("RRA:HWPREDICT:%d:%f:%f:%d" %
                (record_rows, self.alpha, self.beta, season_rows))

        rrdtool.create(self.rrdfile, *args)
        rrdtool.tune(self.rrdfile, "--gamma", str(self.gamma),
                "--gamma-deviation", str(self.gamma))
        self.validate()

    def validate(self):
        info = rrdtool.info(self.rrdfile)
        assert info['step'] == self.step
        assert info['ds']['default']['type'] == self.type
        assert info['ds']['default']['minimal_heartbeat'] == self.step*2
        for rra in info['rra']:
            if rra['cf'] in ('AVERAGE', 'MAX'):
                assert rra['xff'] == 0.5

    def update(self, time, value):
        try:
            float(value)
        except ValueError:
            # Value is not a number so mark it unknown.
            value = "U"
        log.debug("Updating %s with %s" % (self.rrdfile, value))
        self.logfile.write("%s %s\n" % (time, value))
        rrdtool.update(self.rrdfile, "%s:%s" % (time, value))

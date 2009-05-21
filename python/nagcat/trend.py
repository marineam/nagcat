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

try:
    import rrdtool
except ImportError:
    rrdtool = None

import coil
from nagcat import errors, log, util

_rradir = None

def init(dir):
    global _rradir
    assert dir

    if rrdtool is None:
        raise errors.InitError("The python module 'rrdtool' is not installed")

    if not os.path.exists(dir):
        try:
            os.makedirs(dir)
        except OSError, ex:
            raise errors.InitError("Cannot create %s: %s" % (repr(dir), ex))

    if not os.path.isdir(dir):
        raise errors.InitError("%s is not a directory!" % repr(dir))

    if not os.access(dir, os.R_OK | os.W_OK | os.X_OK):
        raise errors.InitError(
                "%s is not readable and/or writeable!" % repr(dir))

    _rradir = dir

def enabled():
    return bool(_rradir)

class Trend(object):

    #: Valid rrdtool data source types
    TYPES = ("GAUGE", "COUNTER", "DERIVE", "ABSOLUTE")

    #: RRAs required for graphing, (period, interval) in seconds
    RRAS = ((1440, 60),         # 4 hours of 1 minute intervals
            (86400, 300),       # 1 day of 5 minute intervals
            (604800, 1800),     # 7 days of 30 minute intervals
            (2678400, 7200),    # 31 days of 2 hour intervals
            (31622400, 86400))  # 366 days of 1 day intervals

    def __init__(self, conf, rradir=None, start=None):
        self._step = util.Interval(conf.get("repeat", "1m")).seconds
        self._ds_list = {'_state': {'type': "GAUGE"}}
        self._start = start

        def parse_ds(ds_name, ds_conf):
            if 'trend' not in ds_conf:
                return

            # Only type supported right now
            new = { 'type': ds_conf['trend.type'].upper() }

            if new['type'] not in self.TYPES:
                raise errors.ConfigError(ds_conf['trend'],
                        "Invalid type: %s" % new['type'])

            self._ds_list[ds_name] = new

        parse_ds('_result', conf)

        if conf['query.type'] == "compound":
            for subname, subconf in conf['query']:
                if not isinstance(subconf, coil.struct.Struct):
                    continue
                parse_ds(subname, subconf)
        else:
            parse_ds('query', conf['query'])

        # Default to a 1 minute step when repeat is useless
        if self._step == 0:
            self._step = 60

        if rradir is None:
            rradir = _rradir
        self._rradir = os.path.join(rradir, conf['host'])
        self._rrafile = os.path.join(self._rradir, "%s.rrd" % conf['name'])

        if not os.path.exists(self._rradir):
            try:
                os.makedirs(self._rradir)
            except OSError, ex:
                raise errors.InitError("Cannot create directory %s: %s" %
                        (self._rradir, ex))

        if os.path.exists(self._rrafile):
            self.validate()
        else:
            self.create()

    def create(self):
        # For now just create archives with the minimal data required
        # to generate cacti graphs since that's where the data will be
        # displayed. More options can be added later...
        log.info("Creating RRA: %s", self._rrafile)

        args = ["--step", str(self._step)]

        if self._start:
            args += ["--start", str(self._start)]

        for ds_name, ds_conf in self._ds_list.iteritems():
            args.append("DS:%s:%s:%d:U:U"
                    % (ds_name, ds_conf['type'], self._step*2))

        for period, interval in self.RRAS:
            if interval < self._step:
                continue
            steps = interval // self._step
            rows = period // steps
            args.append("RRA:MAX:0.5:%d:%d" % (steps, rows))
            args.append("RRA:AVERAGE:0.5:%d:%d" % (steps, rows))

        # The seasonal period is defined in terms of data points.
        # Save 5 seasons of data for now, not sure what the best value is...
        # XXX: Disabled for now...
        #season_rows = self.season // self.step
        #record_rows = season_rows * 5
        #args.append("RRA:HWPREDICT:%d:%f:%f:%d" %
        #        (record_rows, self.alpha, self.beta, season_rows))

        rrdtool.create(self._rrafile, *args)
        #rrdtool.tune(self.rradir, "--gamma", str(self.gamma),
        #        "--gamma-deviation", str(self.gamma))
        self.validate()

    def validate(self):
        info = rrdtool.info(self._rrafile)
        assert info['step'] == self._step
        # This interface changed between versions of rrdtool... lame :-(
        #assert info['ds']['default']['type'] == self.type
        #assert info['ds']['default']['minimal_heartbeat'] == self.step*2
        #for rra in info['rra']:
        #    if rra['cf'] in ('AVERAGE', 'MAX'):
        #        assert rra['xff'] == 0.5

    def update(self, report):
        ds_values = {}

        for ds_name, ds_conf in self._ds_list.iteritems():
            if ds_name == "_state":
                value = report['state_id']
            elif ds_name == "_result":
                value = report['output']
            else:
                value = report['results'][ds_name]

            try:
                value = float(value)
            except ValueError:
                # Value is not a number so mark it unknown.
                value = "U"

            if value != "U" and ds_conf['type'] in ("COUNTER", "DERIVE"):
                value = int(value)

            ds_values[ds_name] = str(value)

        assert ds_values
        names = ":".join(ds_values.iterkeys())
        values = ":".join(ds_values.itervalues())

        log.debug("Updating %s with %s %s", self._rrafile, names, values)
        try:
            rrdtool.update(self._rrafile, "-t", names,
                    "%s:%s" % (report['time'], values))
        except Exception, ex:
            log.error("rrdupdate failed: %s" % ex)

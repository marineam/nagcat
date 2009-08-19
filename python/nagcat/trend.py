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
import time

try:
    import rrdtool
except ImportError:
    rrdtool = None

import coil
from nagcat import errors, log, util

class MismatchError(errors.InitError):
    """RRDTool archive mismatch"""

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

def _rrdtool_info(rrd_file):
    """Wrapper around rrdtool.info() for version compatibility.

    RRDTool changed the format of the data returned by rrdtool.info()
    in >= 1.3 to make it more annoying but similar to the command line
    tool and other language bindings. To make things even better there
    isn't a handy __version__ attribute in <= 1.4 to test.
    """

    new = {'ds': {}, 'rra': {}}
    def parse_ds(key, value):
        match = re.match(r'^ds\[([^\]]+)\]\.(\w+)$', key)
        name = match.group(1)
        attr = match.group(2)

        if name not in new['ds']:
            new['ds'][name] = {attr: value}
        else:
            new['ds'][name][attr] = value

    def parse_rra(key, value):
        # Currently we don't care about cdp_prep so just skip
        if 'cdp_prep' in key:
            return

        match = re.match(r'^rra\[(\d+)\]\.(\w+)$', key)
        index = int(match.group(1))
        attr = match.group(2)

        if index not in new['rra']:
            new['rra'][index] = {attr: value}
        else:
            new['rra'][index][attr] = value

    old = rrdtool.info(rrd_file)

    # Verify that we actually got some data back
    if 'step' not in old:
        raise errors.InitError("Unknown RRDTool info format")

    # Check which version we are probably using
    # <= 1.2, nothing to do!
    if 'ds' in old:
        return old

    # >= 1.3, convert to the easier to use 1.2 format :-(
    for key, value in old.iteritems():
        if key.startswith('ds'):
            parse_ds(key, value)
        elif key.startswith('rra'):
            parse_rra(key, value)
        else:
            new[key] = value

    # Convert rra from a dict to a sorted list
    items = new['rra'].items()
    items.sort()
    new['rra'] = []
    for i, value in items:
        new['rra'].append(value)

    return new

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
            if 'trend' not in ds_conf or 'type' not in ds_conf['trend']:
                return

            # Only type supported right now
            new = { 'type': ds_conf['trend.type'].upper() }

            if new['type'] not in self.TYPES:
                raise errors.ConfigError(ds_conf['trend'],
                        "Invalid type: %s" % new['type'])

            self._ds_list[ds_name] = new

        parse_ds('_result', conf)

        if conf['query.type'] == "compound":
            for subname, subconf in conf['query'].iteritems():
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

        coil_file = os.path.join(self._rradir, "%s.coil" % conf['name'])
        try:
            coil_fd = open(coil_file, 'w')
            coil_fd.write('%s\n' % conf)
            coil_fd.close()
        except (IOError, OSError), ex:
            raise errors.InitError("Cannot write to %s: %s" % (coil_file, ex))

        if os.path.exists(self._rrafile):
            try:
                self.validate()
            except MismatchError:
                self.replace()
        else:
            self.create()

    def replace(self):
        assert os.path.exists(self._rrafile)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        new_file = "%s.%s" % (self._rrafile, timestamp)

        log.info("RRA has changed, saving old file: %s" % new_file)
        os.rename(self._rrafile, new_file)
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
            rows = period // (steps * self._step)
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
        info = _rrdtool_info(self._rrafile)

        if info['step'] != self._step:
            raise MismatchError("step has changed")

        new = set(self._ds_list.keys())
        old = set(info['ds'].keys())
        if new != old:
            raise MismatchError("data source list has changed")

        for ds_name, ds_conf in self._ds_list.iteritems():
            ds_old = info['ds'][ds_name]

            if ds_conf['type'] != ds_old['type']:
                raise MismatchError("data source type has changed")

            if self._step*2 != ds_old['minimal_heartbeat']:
                raise MismatchError("data source heartbeat has changed")

            if ds_old['min'] is not None or ds_old['max'] is not None:
                raise MismatchError("data source min/max was set")

        old = list(info['rra'])
        for period, interval in self.RRAS:
            if interval < self._step:
                continue

            steps = interval // self._step
            rows = period // (steps * self._step)
            rra_max = old.pop(0)
            rra_avg = old.pop(0)

            if rra_max['cf'] != 'MAX':
                raise MismatchError("rra has an unexpected function")
            if rra_avg['cf'] != 'AVERAGE':
                raise MismatchError("rra has an unexpected function")

            for rra in (rra_max, rra_avg):
                if rra['pdp_per_row'] != steps:
                    MismatchError("rra interval has changed")
                if rra['rows'] != rows:
                    MismatchError("rra period has changed")
                if rra['xff'] != 0.5:
                    MismatchError("rra xff has changed")

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
            except:
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
            log.error("rrdupdate for %s failed: %s" % (self._rrafile, ex))

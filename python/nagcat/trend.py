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
import shutil
import tempfile

try:
    import rrdtool
except ImportError:
    rrdtool = None
else:
    from twirrdy import RRDToolError
    from twirrdy.twist import RRDTwistedAPI

import coil
from nagcat import errors, log, util

class MismatchError(errors.InitError):
    """RRDTool archive mismatch"""

class TrendMaster(object):

    def __init__(self, rradir, rrdcache=None):
        if rrdtool is None:
            raise errors.InitError(
                    "The python module 'rrdtool' is not installed")

        if not os.path.exists(rradir):
            try:
                os.makerradirs(rradir)
            except OSError, ex:
                raise errors.InitError("Cannot create %r: %s" % (rradir, ex))
        elif not os.path.isdir(rradir):
            raise errors.InitError("%r is not a directory!" % rradir)
        elif not os.access(rradir, os.R_OK | os.W_OK | os.X_OK):
            raise errors.InitError(
                    "%r is not readable and/or writeable!" % rradir)

        self._rradir = rradir
        self._rrdapi = RRDTwistedAPI()
        if rrdcache:
            self._rrdapi.open(rrdcache)

    def setup_test_trending(self, testobj, testconf):
        """Setup a Trend object for the given test."""
        trendobj = Trend(testconf, self._rradir, rrdapi=self._rrdapi)
        testobj.addReportCallback(trendobj.update)

_master = None

def init(rradir, rrdcache=None):
    global _master
    _master = TrendMaster(rradir, rrdcache)

def addTrend(testobj, testconf):
    """Setup a Trend object for the given test.

    Does nothing if trending is not enabled.
    """
    if not _master:
        return
    _master.setup_test_trending(testobj, testconf)


# Just to make definitions below easier to read
_min  = 60
_hour = _min*60
_day  = _hour*24
_week = _day*7
_mon  = _day*31
_year = _day*366

class Trend(object):

    #: Valid rrdtool data source types
    TYPES = ("GAUGE", "COUNTER", "DERIVE", "ABSOLUTE")

    #: RRAs required for graphing, (interval: period) in seconds
    RRAS = {_min:    _day*2,    # 1 minute intervals for 2 days
            _min*5:  _week*2,   # 5 minute intervals for 2 weeks
            _min*30: _mon*2,    # 30 minute intervals for 2 months
            _hour*2: _year,     # 2 hour intervals for 1 year
            _day:    _year*6}   # 1 day intervals for 6 years

    def __init__(self, conf, rradir, start=None, rrdapi=None):
        self._step = util.Interval(conf.get("repeat", "1m")).seconds
        self._ds_list = {'_state': {'type': "GAUGE", 'min': None, 'max': None}}
        # _ds_order is the order in the actual file and is set in validate()
        self._ds_order = None
        self._start = start

        if rrdapi is None:
            self._rrdapi = RRDTwistedAPI()
        else:
            self._rrdapi = rrdapi

        def parse_limit(new, old, key):
            limit = old.get(key, None)
            if limit is not None:
                try:
                    limit = float(limit)
                except ValueError:
                    raise errors.ConfigError(old,
                            "Invalid %s: %s" % (key, limit))
            new[key] = limit

        def parse_ds(ds_name, ds_conf):
            if 'trend' not in ds_conf or 'type' not in ds_conf['trend']:
                return

            ds_conf['trend'].expand()

            new = { 'type': ds_conf['trend.type'].upper() }
            if new['type'] not in self.TYPES:
                raise errors.ConfigError(ds_conf['trend'],
                        "Invalid type: %s" % new['type'])

            parse_limit(new, ds_conf['trend'], 'min')
            parse_limit(new, ds_conf['trend'], 'max')

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

        rras = conf.get('trend.rra', None)
        clean = re.compile('^[^\d]*').sub
        self._rras = self.RRAS.copy()
        if isinstance(rras, coil.struct.Struct):
            for interval, period in rras.iteritems():
                interval = clean('', interval)
                try:
                    interval = int(util.Interval(interval))
                except util.IntervalError:
                    raise errors.ConfigError(conf,
                            "Invalid RRA interval: %r" % interval)
                try:
                    period = int(util.Interval(period))
                except util.IntervalError:
                    raise errors.ConfigError(conf,
                            "Invalid RRA period: %r" % period)
                if not period:
                    del self._rras[interval]
                else:
                    self._rras[interval] = period
        elif rras is not None:
            raise errors.ConfigError(conf,
                    "trend.rra must be a struct, got: %r" % rras)

        self._rradir = os.path.abspath(os.path.join(rradir, conf['host']))
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

        log.debug("Loaded trending config: %s", self._ds_list)

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
            ds_min = ds_conf['min']
            if ds_min is None:
                ds_min = 'U'
            ds_max = ds_conf['max']
            if ds_max is None:
                ds_max = 'U'
            args.append("DS:%s:%s:%d:%s:%s" % (ds_name,
                ds_conf['type'], self._step*2, ds_min, ds_max))

        for interval, period in sorted(self._rras.iteritems()):
            if interval < self._step:
                continue
            steps = interval // self._step
            rows = period // interval
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
        info = self._rrdapi.info(self._rrafile, defer=False)
        self._ds_order = info['ds'].keys()

        if info['step'] != self._step:
            raise MismatchError("step has changed")

        new = set(self._ds_list.keys())
        old = set(self._ds_order)
        if new != old:
            raise MismatchError("data source list has changed")

        def check_limit(new, old, key):
            limit = new[key]
            if limit != old[key]:
                raise MismatchError("data source min/max changed")

        for ds_name, ds_conf in self._ds_list.iteritems():
            ds_old = info['ds'][ds_name]

            if ds_conf['type'] != ds_old['type']:
                raise MismatchError("data source type has changed")

            if self._step*2 != ds_old['minimal_heartbeat']:
                raise MismatchError("data source heartbeat has changed")

            check_limit(ds_conf, ds_old, 'min')
            check_limit(ds_conf, ds_old, 'max')

        old = list(info['rra'])
        index = 0
        for interval, period in sorted(self._rras.iteritems()):
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

            for i, rra in enumerate((rra_max, rra_avg)):
                if rra['pdp_per_row'] != steps:
                    raise MismatchError("rra interval has changed")
                if rra['rows'] != rows:
                    self.resize(index+i, rra['rows'], rows)
                if rra['xff'] != 0.5:
                    raise MismatchError("rra xff has changed")
            index += 2
        if old:
            raise MismatchError("%d unexpected RRAs" % len(old))

    def resize(self, index, old, new):
        """Wrapper around rrdtool resize to add/remove rows from an RRA"""

        log.info("Resizing RRA %d in %s from %d to %d rows" %
                (index, self._rrafile, old, new))

        assert old != new
        diff = abs(old - new)
        if new > old:
            dir = "GROW"
        else:
            dir = "SHRINK"

        # resize *always* writes to ./resize.rrd which isn't
        # particularly helpful but we can work with it.
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp(dir=self._rradir)
        try:
            os.chdir(tmp)
            rrdtool.resize(self._rrafile, str(index), dir, str(diff))
            shutil.copymode(self._rrafile, "resize.rrd")
            os.rename("resize.rrd", self._rrafile)
        finally:
            os.chdir(cwd)
            os.rmdir(tmp)

    def update(self, report):
        update_values = []

        for ds_name in self._ds_order:
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

            ds_conf = self._ds_list[ds_name]
            if value != "U" and ds_conf['type'] in ("COUNTER", "DERIVE"):
                value = int(value)

            update_values.append(value)

        def errcb(failure):
            if isinstance(failure.value, RRDToolError):
                log.error("Update to %s failed: %s",
                        self._rrafile, failure.value)
            else:
                log.error(str(failure))

        assert update_values
        log.debug("Updating %s with %s", self._rrafile, update_values)
        deferred = self._rrdapi.update(
                self._rrafile,report['time'], update_values)
        deferred.addErrback(errcb)

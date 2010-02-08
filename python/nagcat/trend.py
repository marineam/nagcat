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
import ctypes
import tempfile

from twisted.internet import reactor

try:
    rrd_th = ctypes.CDLL("librrd_th.so", ctypes.RTLD_GLOBAL)
    rrd_th.rrd_get_error.restype = ctypes.c_char_p
except OSError:
    rrd_th = None

try:
    import rrdtool
except ImportError:
    rrdtool = None

import coil
from nagcat import errors, log, util

class MismatchError(errors.InitError):
    """RRDTool archive mismatch"""

class RRDToolError(Exception):
    """Error in a rrd_th call"""

    def __init__(self):
        error = str(rrd_th.rrd_get_error())
        Exception.__init__(self, error)
        rrd_th.rrd_clear_error()

_rradir = None

def init(dir):
    global _rradir
    assert dir

    if rrdtool is None:
        raise errors.InitError("The python module 'rrdtool' is not installed")

    if rrd_th is None:
        raise errors.InitError("Cannot load the thread-safe rrdtool library")

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

def rrdtool_info(rrd_file):
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

    if not os.path.isfile(rrd_file):
        raise errors.InitError("RRDTool file does not exists: %s" % rrd_file)

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

def rrdtool_update(filename, template, *args):
    """Thread safe rrdtool update function.

    The RRDTool Python bindings do not use the thread-safe library.
    This is a wrapper to the thread-save version using ctypes.
    """

    # Just a quick sanity check
    assert filename.__class__ is str
    assert template.__class__ is str

    argc = len(args)
    argv_t = ctypes.c_char_p * argc
    argv = argv_t()
    for i, arg in enumerate(args):
        assert arg.__class__ is str
        argv[i] = arg

    if rrd_th.rrd_update_r(filename, template, argc, argv):
        raise RRDToolError()


def addTrend(testobj, testconf):
    """Setup a Trend object for the given test.

    Does nothing if trending is not enabled.
    """
    if _rradir:
        trendobj = Trend(testconf)
        testobj.addReportCallback(trendobj.update)

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
        self._ds_list = {'_state': {'type': "GAUGE", 'min': None, 'max': None}}
        self._start = start

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

            # Only type supported right now
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
        info = rrdtool_info(self._rrafile)

        if info['step'] != self._step:
            raise MismatchError("step has changed")

        new = set(self._ds_list.keys())
        old = set(info['ds'].keys())
        if new != old:
            raise MismatchError("data source list has changed")

        def check_limit(new, old, key):
            limit = new[key]
            if limit == 'U':
                limit = None
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

        def do_update():
            log.debug("Updating %s with %s %s", self._rrafile, names, values)
            try:
                rrdtool_update(self._rrafile, names,
                        "%s:%s" % (report['time'], values))
            except RRDToolError, ex:
                log.error("rrd update to %s failed: %s" % (self._rrafile, ex))

        reactor.callInThread(do_update)

class Colorator(object):
    """A helper for picking graph colors"""

    COLORS = ('#002A8F','#DA4725','#008A6D','#00BD27','#CCBB00','#F24AC8')

    def __init__(self):
        self.color_idx = 0

    def next(self):
        self.color_idx += 1
        return Colorator.COLORS[(self.color_idx - 1) % len(Colorator.COLORS)]

def rrd_esc(string):
    """Escape : so rrd arguments parse properly"""
    return string.replace(':', r'\:')

class Graph(object):

    def __init__(self, dir, host, rrd, period="day"):
        self.rrd = rrd
        self.host = host
        path = "%s/%s/%s" % (dir, host, rrd)
        self.rrd_path = "%s.rrd" % path
        self.info = rrdtool_info(self.rrd_path)
        self.color = Colorator()
        self.period = period

        try:
            self.conf = coil.parse_file("%s.coil" % path)
        except IOError, ex:
            raise errors.InitError("Unable to read coil file: %s" % ex)

        if period not in ('day', 'week', 'month', 'year'):
            raise ValueError("Invalid period parameter")

        self.args = []
        self.ds = []
        self._init_args()
        self._init_ds()
        self._init_ds_args()

    def _init_ds(self):
        """Find the data sources referred to in the coil config."""

        self.ds.append('_state')

        if self.conf.get('trend.type', False):
            self.ds.append('_result')

        if self.conf['query.type'] == 'compound':
            for name, sub in self.conf['query'].iteritems():
                if (isinstance(sub, coil.struct.Struct) and
                        sub.get('trend.type', False)):
                    self.ds.append(name)

        elif self.conf.get('query.trend.type', False):
            self.ds.append('query')

    def _init_args(self):
        """Build the initial part of the rrdgraph args
        before the data source arguments
        """

        title = self.conf.get('trend.title',
                "%s - %s" % (self.host, self.rrd))
        axis_min = self.conf.get('trend.axis_min', "0")
        axis_max = self.conf.get('trend.axis_max', None)
        axis_label = self.conf.get('trend.axis_label', None)
        base = self.conf.get('trend.base', 1000)

        self.args = ["-s", "-1%s" % self.period,
                     "--title", title,
                     "--alt-autoscale-max", "--alt-y-grid",
                     "--lower-limit", str(axis_min)]
        if axis_max:
            self.args += ["--upper-limit", str(axis_max)]
        if axis_label:
            self.args += ["--vertical-label", str(axis_label)]
        if base:
            self.args += ["--base", str(base)]

        # Add the _state ds that all of them have
        self.args += ["DEF:_state=%s:_state:MAX" % rrd_esc(self.rrd_path),
                      "CDEF:_state_ok=_state,0,EQ",
                      "CDEF:_state_warn=_state,1,EQ",
                      "CDEF:_state_crit=_state,2,EQ",
                      "CDEF:_state_unkn=_state,3,EQ",
                      "TICK:_state_ok#ddffcc:1.0:Ok",
                      "TICK:_state_warn#ffffcc:1.0:Warning",
                      "TICK:_state_crit#ffcccc:1.0:Critical",
                      "TICK:_state_unkn#ffcc55:1.0:Unknown\\n"]

    def _init_ds_args(self):
        """Build the rrdgraph args for all the known data sources"""

        extra = set(self.ds)
        for ds in self.ds:
            if ds not in self.info['ds']:
                self.args.append("COMMENT:WARNING\: Missing DS %s\\n" % ds)
                continue

            extra.remove(ds)

            if ds == '_state':
                continue

            self.args += self._one_ds_args(ds)

        for ds in extra:
            self.args.append("COMMENT:WARNING\: Unexpected DS %s\\n" % ds)

    def _one_ds_args(self, ds):
        """Build the arguments for a single data source"""

        args = []

        if ds == "_result":
            dsconf = self.conf
            label = dsconf.get('trend.label', dsconf.get('label', 'Result'))
            default_color = "#000000"
        elif ds == 'query' and self.conf['query.type'] != 'compound':
            dsconf = self.conf
            label = dsconf.get('query.trend.label',
                    dsconf.get('query.label', dsconf.get('label', 'Result')))
            default_color = "#000000"
        else:
            dsconf = self.conf['query'][ds]
            label = dsconf.get('trend.label',
                    dsconf.get('label', ds.capitalize()))
            default_color = self.color.next()

        scale = int(dsconf.get('trend.scale', 0))
        if scale:
            args.append("DEF:_raw_%s=%s:%s:AVERAGE" %
                    (ds, rrd_esc(self.rrd_path), ds))
            args.append("CDEF:%s=_raw_%s,%d,*" % (ds, ds, scale))
        else:
            args.append("DEF:%s=%s:%s:AVERAGE" %
                    (ds, rrd_esc(self.rrd_path), ds))

        if dsconf.get('trend.stack', False):
            stack = "STACK"
        else:
            stack = ""

        color = dsconf.get('trend.color', default_color)
        display = dsconf.get('trend.display', 'line').lower()
        if display == 'area':
            args.append("AREA:%s%s:%s:%s" % (ds, color, rrd_esc(label), stack))
        elif display == 'line':
            args.append("LINE2:%s%s:%s:%s" % (ds, color, rrd_esc(label), stack))
        else:
            raise ValueError("Invalid display value")

        prefix = max(7 - len(label), 0) * " "
        args.append("VDEF:_last_%s=%s,LAST" % (ds, ds))
        args.append("VDEF:_avg_%s=%s,AVERAGE" % (ds, ds))
        args.append("VDEF:_max_%s=%s,MAXIMUM" % (ds, ds))
        args.append("GPRINT:_last_%s:%sCurrent\\:%%8.2lf%%s" % (ds, prefix))
        args.append("GPRINT:_avg_%s:Average\\:%%8.2lf%%s" % ds)
        args.append("GPRINT:_max_%s:Maximum\\:%%8.2lf%%s\\n" % ds)

        return args

    def graph(self, width=500, height=120):
        fd, path = tempfile.mkstemp('.png')
        try:
            rrdtool.graph(path, "-a", "PNG", "--width", str(width),
                    "--height", str(height), *self.args)
        except:
            os.close(fd)
            raise
        finally:
            os.unlink(path)

        fd = os.fdopen(fd)
        png = fd.read()
        fd.close()

        return png


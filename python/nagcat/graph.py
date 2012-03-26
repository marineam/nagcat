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

"""RRDTool Graphing"""

import os
import stat
import tempfile

try:
    import rrdtool
except ImportError:
    rrdtool = None

import coil
import twirrdy
from nagcat import errors

def available():
    """Returns False if rrdtool is not available"""
    return rrdtool is not None

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
        api = twirrdy.RRDBasicAPI()
        self.rrd = rrd
        self.host = host
        path = "%s/%s/%s" % (dir, host, rrd)
        self.rrd_path = "%s.rrd" % path
        self.info = api.info(self.rrd_path)
        self.color = Colorator()
        self.period = period

        try:
            coil_fd = open("%s.coil" % path)
            try:
              coil_stat = os.fstat(coil_fd.fileno())
              self.private = not (coil_stat.st_mode & stat.S_IROTH)
              self.conf = coil.parse(coil_fd.read())
            finally:
              coil_fd.close()
        except (IOError, OSError), ex:
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

        scale = float(dsconf.get('trend.scale', 0))
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

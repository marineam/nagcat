#!/usr/bin/env python

import cgitb
cgitb.enable()

import sys
import os
import cgi
import coil
import rrdtool

from nagcat.trend import rrdtool_info

class Colorator:
    COLORS = ('#002A8F','#DA4725','#008A6D','#00BD27','#CCBB00','#F24AC8')

    def __init__(self):
        self.color_idx = 0

    def next(self):
        self.color_idx += 1
        return Colorator.COLORS[(self.color_idx - 1) % len(Colorator.COLORS)]

def rrd_esc(string):
    """Escape : so rrd arguments parse properly"""
    return string.replace(':', r'\:')

def pull_cgi_data(cgi_store):
    """Pull data from CGI variables, validating the inputs."""
    assert 'host' in cgi_store, "Host parameter not found"
    assert 'rrd' in cgi_store, "RRD parameter not found"
    host = cgi_store.getfirst('host').translate(None, "/.")
    rrd = cgi_store.getfirst('rrd').translate(None, "/.")

    if 'period' in cgi_store:
        period = cgi_store.getfirst('period')
        assert period in ('day', 'week', 'month', 'year'), "Invalid period parameter"
    else:
        period = "day"
    return (host, rrd, period)

def collect_ds_queries(conf):
    """Returns a set of the data sources referred to in the coil config."""
    data_sources = ['_state']
    if conf.get('trend.type', False):
        data_sources.append('_result')
    if conf['query.type'] == 'compound':
        for name, sub in conf['query'].iteritems():
            if isinstance(sub, coil.struct.Struct) and sub.get('trend.type', False):
                data_sources.append(name)
    elif conf.get('query.trend.type', False):
        data_sources.append('query')

    return data_sources

def build_rrd_path(host, rrd):
    """Returns the RRD pathname given the host and rrd"""
    rrd_path = "%s/%s/%s.rrd" % (os.getenv('NAGCAT_RRA_DIR'), host, rrd)
    assert os.path.isfile(rrd_path), "RRD file does not exist"
    return rrd_path

def pull_conf_data(host, rrd):
    """Pull data from the coil configuration"""
    coil_path = "%s/%s/%s.coil" % (os.getenv('NAGCAT_RRA_DIR'), host, rrd)
    assert os.path.isfile(coil_path), "Coil configuration does not exist"
    conf = coil.parse_file(coil_path)

    return (conf, collect_ds_queries(conf))

def configure_graph_display(conf, ds, colorator):
    """Given the configuration and a datasource, outputs the various
    graphing options that should be used in its display.  Takes a
    Colorator object to handle graph coloring when no color is
    explicitly specified."""
    if ds == "_result":
        dsconf = conf
        label = conf.get('trend.label', conf.get('label', 'Result'))
        default_color = "#000000"
    elif ds == 'query' and conf['query.type'] != 'compound':
        dsconf = conf
        label = dsconf.get('query.trend.label', dsconf.get('query.label',
            conf.get('label', 'Result')))
        default_color = "#000000"
    else:
        dsconf = conf['query.%s' % ds]
        label = dsconf.get('trend.label', dsconf.get('label', ds.capitalize()))
        default_color = colorator.next()

    color = dsconf.get('trend.color', default_color)
    scale = int(dsconf.get('trend.scale', 0))
    display = dsconf.get('trend.display', 'line').lower()
    assert display in ('line', 'area'), "Invalid display configured"
    stack = dsconf.get('trend.stack', False)

    return (label, color, scale, display, stack)

def graph_config_to_arguments(ds, rrd_path, label, color, scale, display, stack):
    """Returns rrdgraph arguments corresponding to the graphing
    configuration of a given data source"""
    # Add graph config to rrdgraph command-line arguments
    result = []
    if scale:
        result.append("DEF:_raw_%s=%s:%s:AVERAGE" % (ds, rrd_esc(rrd_path), ds))
        result.append("CDEF:%s=_raw_%s,%d,*" % (ds, ds, scale))
    else:
        result.append("DEF:%s=%s:%s:AVERAGE" % (ds, rrd_esc(rrd_path), ds))

    if stack:
        stack = "STACK"
    else:
        stack = ""

    if display == 'area':
        result.append("AREA:%s%s:%s:%s" % (ds, color, rrd_esc(label), stack))
    elif display == 'line':
        result.append("LINE2:%s%s:%s:%s" % (ds, color, rrd_esc(label), stack))

    prefix = max(7 - len(label), 0) * " "
    result.append("VDEF:_last_%s=%s,LAST" % (ds, ds))
    result.append("VDEF:_avg_%s=%s,AVERAGE" % (ds, ds))
    result.append("VDEF:_max_%s=%s,MAXIMUM" % (ds, ds))
    result.append("GPRINT:_last_%s:%sCurrent\\:%%8.2lf%%s" % (ds, prefix))
    result.append("GPRINT:_avg_%s:Average\\:%%8.2lf%%s" % ds)
    result.append("GPRINT:_max_%s:Maximum\\:%%8.2lf%%s\\n" % ds)

    return result

def build_rrd_args_preamble(rrd_path, period, conf):
    """Build the initial part of the rrdgraph args before the data
    source arguments"""
    title = conf.get('trend.title', "%s - %s" % (host, rrd))
    axis_min = str(conf.get('trend.axis_min', "0"))
    axis_max = conf.get('trend.axis_max', None)
    axis_label = conf.get('trend.axis_label', None)
    base = conf.get('trend.base', 1000)

    rrd_args =  [ "-s", "-1%s" % (period,),
                  "--title", rrd_esc(title),
                  "--lower-limit", axis_min]
    if base and base != 1000:
        rrd_args += ["--base", str(base)]
    if axis_max:
        rrd_args += ["--upper-limit", str(axis_max)]
    if axis_label:
        rrd_args += ["--vertical-label", str(axis_label)]

    # Add RRD preamble
    rrd_args += ["DEF:_state=%s:_state:MAX" % rrd_esc(rrd_path),
                 "CDEF:_state_ok=_state,0,EQ",
                 "CDEF:_state_warn=_state,1,EQ",
                 "CDEF:_state_crit=_state,2,EQ",
                 "CDEF:_state_unkn=_state,3,EQ",
                 "TICK:_state_ok#ddffcc:1.0:Ok",
                 "TICK:_state_warn#ffffcc:1.0:Warning",
                 "TICK:_state_crit#ffcccc:1.0:Critical",
                 "TICK:_state_unkn#ffcc55:1.0:Unknown\\n"]
    return rrd_args

def build_rrd_args(rrd_path, period, conf, data_sources):
    """Returns the arguments to be passed to rrdgraph in order to
    graph the given data sources with the given options."""

    extra = set(data_sources)
    rrd_args = build_rrd_args_preamble(rrd_path, period, conf)

    # Pull info on the RRD database
    info = rrdtool_info(rrd_path)
    colorator = Colorator()
    for ds in data_sources:
        if ds not in info['ds']:
            rrd_args.append("COMMENT:WARNING\: Missing DS %s\\n" % (rrd_esc(ds),))
            continue

        extra.remove(ds)

        if ds == '_state':
            continue

        (label, color, scale, display, stack) = configure_graph_display(conf, ds, colorator)
        rrd_args += graph_config_to_arguments(ds, rrd_path, label, color, scale, display, stack)

    for ds in extra:
        rrd_args.append("COMMENT:WARNING\: Unexpected DS %s\\n" % (rrd_esc(ds),))

    return rrd_args

def output_graph(rrd_args):
    """Outputs the graph to the HTTP server given the arguments to
    rrdgraph."""
    print "Content-Type: image/png"
    print
    rrdtool.graph("-", "-a", "PNG",
                  "--width=500", "--height=120",
                  "--alt-autoscale-max", "--alt-y-grid",
                  *rrd_args)

def argv_to_cgi(argv, cgi_store):
    key=None
    for arg in argv:
        if arg.startswith("--"):
            if key:
                cgi_store.list.append(cgi.MiniFieldStorage(key, True))
            key = arg.replace("--", "", 1)
        else:
            if key:
                cgi_store.list.append(cgi.MiniFieldStorage(key, arg))
            key = None

### Execution
if __name__ == "__main__":
    cgi_store = cgi.FieldStorage()
    argv_to_cgi(sys.argv, cgi_store)
    (host, rrd, period) = pull_cgi_data(cgi_store)
    rrd_path = build_rrd_path(host, rrd)
    (conf, data_sources) = pull_conf_data(host, rrd)
    rrd_args = build_rrd_args(rrd_path, period, conf, data_sources)
    output_graph(rrd_args)

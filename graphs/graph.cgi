#!/usr/bin/env python

import cgitb
cgitb.enable()

import os
import cgi
import coil
import rrdtool

HEAD = "Content-Type: image/png"
COLORS = ('#002A8F','#DA4725','#008A6D','#00BD27','#CCBB00','#F24AC8')

def esc(string):
    """Escape : so rrd arguments parse properly"""
    return string.replace(':', r'\:')

data = cgi.FieldStorage()
assert 'host' in data
assert 'rrd' in data
host = data['host'].value
rrd = data['rrd'].value

if 'period' in data:
    period = data['period'].value
    assert period in ('day', 'week', 'month', 'year')
else:
    period = "day"

rrd_path = "%s/%s/%s.rrd" % (os.getenv('NAGCAT_RRA_DIR'), host, rrd)
coil_path = "%s/%s/%s.coil" % (os.getenv('NAGCAT_RRA_DIR'), host, rrd)
assert os.path.isfile(rrd_path)
assert os.path.isfile(coil_path)

conf = coil.parse_file(coil_path)
# Count the number of queries that should have a ds
ds_configured = set(['_state'])
if conf.get('trend.type', False):
    ds_configured.add('_result')
for name, sub in conf['query'].iteritems():
    if isinstance(sub, coil.struct.Struct) and sub.get('trend.type', False):
        ds_configured.add(name)

args = ["--title", conf.get('trend.title', "%s - %s" % (host, rrd)),
        "--lower-limit", str(conf.get('trend.axis_min', "0"))]
axis_max = conf.get('trend.axis_max', None)
if axis_max:
    args += ["--upper-limit", str(axis_max)]
axis_label = conf.get('trend.axis_label', None)
if axis_label:
    args += ["--vertical-label", str(axis_label)]

info = rrdtool.info(rrd_path)
color_index = 0
stack_started = False
for ds in info['ds']:
    if ds not in ds_configured:
        args.append("COMMENT:WARNING\: Unexpected DS %s\\n" % ds)
        continue

    ds_configured.remove(ds)

    if ds == "_state":
        continue
    elif ds == "_result":
        dsconf = conf
        label = esc(conf.get('trend.label', conf.get('label', 'Result')))
        color = "#000000"
    else:
        dsconf = conf['query.%s' % ds]
        label = esc(dsconf.get('trend.label',
            dsconf.get('label', ds.capitalize())))
        color = COLORS[color_index % len(COLORS)]
        color_index += 1

    color = dsconf.get('trend.color', color)
    scale = int(dsconf.get('trend.scale', 0))
    base = int(dsconf.get('trend.base', 1000))
    display = dsconf.get('trend.display', 'line').lower()
    assert base in (1024, 1000)
    assert display in ('line', 'area')

    if scale:
        args.append("DEF:_raw_%s=%s:%s:AVERAGE" % (ds, esc(rrd_path), ds))
        args.append("CDEF:%s=_raw_%s,%d,*" % (ds, ds, scale))
    else:
        args.append("DEF:%s=%s:%s:AVERAGE" % (ds, esc(rrd_path), ds))

    if display == 'area':
        if stack_started:
            stack = ":STACK"
        else:
            stack = ""
            stack_started = True

        args.append("AREA:%s%s:%s%s" % (ds, color, label, stack))
    elif display == 'line':
        args.append("LINE2:%s%s:%s" % (ds, color, label))
    else:
        assert 0

    prefix = max(7 - len(label), 0) * " "
    args.append("VDEF:_last_%s=%s,LAST" % (ds, ds))
    args.append("VDEF:_avg_%s=%s,AVERAGE" % (ds, ds))
    args.append("VDEF:_max_%s=%s,MAXIMUM" % (ds, ds))
    args.append("GPRINT:_last_%s:%sCurrent\\:%%8.2lf%%s" % (ds, prefix))
    args.append("GPRINT:_avg_%s:Average\\:%%8.2lf%%s" % ds)
    args.append("GPRINT:_max_%s:Maximum\\:%%8.2lf%%s\\n" % ds)

for ds in ds_configured:
    args.append("COMMENT:WARNING\: Missing DS %s\\n" % ds)

print HEAD
print
rrdtool.graph("-", "-a", "PNG", "-s", "-1%s" % period,
        "--width=500", "--height=120",
        "--alt-autoscale-max", "--alt-y-grid",
        "DEF:_state=%s:_state:MAX" % rrd_path,
        "CDEF:_state_ok=_state,0,EQ",
        "CDEF:_state_warn=_state,1,EQ",
        "CDEF:_state_crit=_state,2,EQ",
        "CDEF:_state_unkn=_state,3,EQ",
        "TICK:_state_ok#ddffcc:1.0:Ok",
        "TICK:_state_warn#ffffcc:1.0:Warning",
        "TICK:_state_crit#ffcccc:1.0:Critical",
        "TICK:_state_unkn#ffcc55:1.0:Unknown\\n",
        *args)

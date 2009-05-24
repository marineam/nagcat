#!/usr/bin/env python

import cgitb
cgitb.enable()

import os
import cgi
import rrdtool

HEAD = "Content-Type: image/png"
COLORS = ('#0000FF', '#00FF00')

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
assert os.path.isfile(rrd_path)

color = 0
args = []
info = rrdtool.info(rrd_path)
# Escape : so DEF arguments parse properly
rrd_path = rrd_path.replace(':', r'\:')
for line in info['ds']:
    if line == "_state":
        continue
    elif line == "_result":
        args.append("DEF:_result=%s:_result:AVERAGE" % rrd_path)
        args.append("LINE2:_result#000000:Result")
    else:
        args.append("DEF:%s=%s:%s:AVERAGE" % (line, rrd_path, line))
        args.append("LINE2:%s%s:%s" % (line,
                COLORS[color % len(COLORS)], line.capitalize()))
        color += 1

print HEAD
print
rrdtool.graph("-", "-a", "PNG", "-s", "-1%s" % period,
        "DEF:_state=%s:_state:MAX" % rrd_path,
        "CDEF:_state_ok=_state,0,EQ",
        "CDEF:_state_warn=_state,1,EQ",
        "CDEF:_state_crit=_state,2,EQ",
        "CDEF:_state_unkn=_state,3,EQ",
        "TICK:_state_ok#a0ffa0:1.0:Ok",
        "TICK:_state_warn#ffffa0:1.0:Warning",
        "TICK:_state_crit#ffa0a0:1.0:Critical",
        "TICK:_state_unkn#ffa050:1.0:Unknown",
        *args)

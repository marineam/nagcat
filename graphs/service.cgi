#!/usr/bin/env python

import cgitb
cgitb.enable()

import os
import cgi
import urllib
from glob import glob

from nagcat import nagios_objects

HEAD = "Content-Type: text/html"
PAGE = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
    <title>Nagcat/Nagios Trends - %(host_esc)s - %(service_esc)s</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <h1>%(host_esc)s - %(service_esc)s</h1>
    <div class="%(status)s">%(status)s</div>
    <pre>%(output_esc)s</pre>
    %(graphs)s
</body>
</html>
"""

GRAPHS = """<div>
Today:<br />
<img alt="graph" src="graph.cgi?host=%(host_url)s&amp;rrd=%(service_url)s&amp;period=day" />
</div><div>
This Week:<br />
<img alt="graph" src="graph.cgi?host=%(host_url)s&amp;rrd=%(service_url)s&amp;period=week" />
</div><div>
This Month:<br />
<img alt="graph" src="graph.cgi?host=%(host_url)s&amp;rrd=%(service_url)s&amp;period=month" />
</div><div>
This Year:<br />
<img alt="graph" src="graph.cgi?host=%(host_url)s&amp;rrd=%(service_url)s&amp;period=year" />
</div>
"""

data = cgi.FieldStorage()
assert 'host' in data
host = data['host'].value
host_url = urllib.quote(host)
host_esc = cgi.escape(host)
assert 'service' in data
service = data['service'].value
service_url = urllib.quote(service)
service_esc = cgi.escape(service)

obj_file = os.getenv('NAGIOS_OBJECTS')
stat_file = os.getenv('NAGIOS_STATUS')
host_dir = "%s/%s" % (os.getenv('NAGCAT_RRA_DIR'), host)
assert obj_file and os.path.isfile(obj_file)
assert stat_file and os.path.isfile(stat_file)

service_info = nagios_objects.Parser(stat_file, ('service',),
        {'host_name': host, 'service_description': service})['service'][0]

if service_info['long_plugin_output']:
    output = "%s\n%s" % (service_info['plugin_output'],
            service_info['long_plugin_output'])
    output = output.replace(r'\n', '\n')
    output_esc = cgi.escape(output)
else:
    output_esc = cgi.escape(service_info['plugin_output'])

status = service_info['current_state']
if status == '0':
    status = "Ok"
elif status == '1':
    status = "Warning"
elif status == '2':
    status = "Critical"
else:
    status = "Unknown"

if os.path.isfile("%s/%s.rrd" % (host_dir, service)):
    graphs = GRAPHS % {'host_url': host_url, 'service_url': service_url}
else:
    graphs = ""

print HEAD
print
print PAGE % {'host_esc': host_esc, 'host_url': host_url,
    'service_esc': service_esc, 'service_url': service_url,
    'output_esc': output_esc, 'status': status, 'graphs': graphs}

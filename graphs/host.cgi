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
    <title>Nagcat/Nagios Trends - %(host_esc)s</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <h1>%(host_esc)s</h1>
    <div>%(host_info_esc)s</div>
    <table>
    %(services)s
    </table>
</body>
</html>
"""

SERVICE = """
<tr>
    <td class="%(status)s">
        <a href="service.cgi?host=%(host_url)s&amp;service=%(service_url)s">
            <h3>%(service_esc)s</h3>
        </a>
    </td>
    <td>
        <div>%(status)s - %(output_esc)s</div>
        %(graph)s
    </td>
</tr>
"""

GRAPH = """<div>
<a href="service.cgi?host=%(host_url)s&amp;service=%(service_url)s">
<img alt="graph" src="graph.cgi?host=%(host_url)s&amp;rrd=%(service_url)s" />
</a>
</div>
"""

data = cgi.FieldStorage()
assert 'host' in data
host = data['host'].value
host_url = urllib.quote(host)
host_esc = cgi.escape(host)

obj_file = os.getenv('NAGIOS_OBJECTS')
stat_file = os.getenv('NAGIOS_STATUS')
host_dir = "%s/%s" % (os.getenv('NAGCAT_RRA_DIR'), host)
assert obj_file and os.path.isfile(obj_file)
assert stat_file and os.path.isfile(stat_file)

objects = nagios_objects.ObjectParser(obj_file, ('host',), {'host_name': host})
status = nagios_objects.ObjectParser(stat_file,
        ('host','service'), {'host_name': host})
host_conf = objects['host'][0]
host_info_esc = cgi.escape(host_conf.get('notes', host_conf['alias']))

services = ""
for service in status['service']:
    service_name = service['service_description']
    service_url = urllib.quote(service_name)
    service_esc = cgi.escape(service_name)
    output_esc = cgi.escape(service['plugin_output'])

    status = service['current_state']
    if status == '0':
        status = "Ok"
    elif status == '1':
        status = "Warning"
    elif status == '2':
        status = "Critical"
    else:
        status = "Unknown"

    if os.path.isfile("%s/%s.rrd" % (host_dir, service_name)):
        graph = GRAPH % {'host_url': host_url, 'service_url': service_url}
    else:
        graph = ""

    services += SERVICE % {'service_esc': service_esc,
            'service_url': service_url, 'host_url': host_url,
            'output_esc': output_esc, 'status': status, 'graph': graph}

print HEAD
print
print PAGE % {'host_esc': host_esc, 'host_info_esc': host_info_esc,
        'services': services}

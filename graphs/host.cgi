#!/usr/bin/env python

import cgitb
cgitb.enable()

import os
import cgi
import urllib
from glob import glob

HEAD = "Content-Type: text/html"
PAGE = """<!DOCTYPE html 
     PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
    <title>Nagcat/Nagios Trends - %(host_esc)s</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <h1>%(host_esc)s</h1>
    %(graphs)s
</body>
</html>
"""

GRAPH = """<div>
<h2>%(rrd_esc)s</h2>
<img alt="graph" src="graph.cgi?host=%(host_url)s&rrd=%(rrd_url)s" />
</div>
"""

data = cgi.FieldStorage()
assert 'host' in data
host = data['host'].value
host_url = urllib.quote(host)
host_esc = cgi.escape(host)

host_dir = "%s/%s" % (os.getenv('NAGCAT_RRA_DIR'), host)
assert os.path.isdir(host_dir)

rrd_list = glob("%s/*.rrd" % host_dir)
rrd_list.sort()

graphs = ""
for rrd in rrd_list:
    rrd_name = os.path.basename(rrd)[:-4]
    graphs += GRAPH % { 'host_url': host_url,
            'rrd_esc': cgi.escape(rrd_name),
            'rrd_url':  urllib.quote(rrd_name)}
    
print HEAD
print
print PAGE % {'host_esc': host_esc, 'graphs': graphs}

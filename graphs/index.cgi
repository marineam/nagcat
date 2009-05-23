#!/usr/bin/env python

import cgitb
cgitb.enable()

import os
import cgi
import urllib

HEAD = "Content-Type: text/html"
PAGE = """<!DOCTYPE html 
     PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
    <title>Nagcat/Nagios Trends - Hosts</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <h1>Hosts</h1>
    <ul>
        %(hosts)s
    </ul>
</body>
</html>
"""

HOST = """<li><a href="host.cgi?host=%(host_url)s">%(host_esc)s</a></li>\n"""

rra_dir = os.getenv('NAGCAT_RRA_DIR')
assert rra_dir
assert os.path.isdir(rra_dir)

host_list = os.listdir(rra_dir)
host_list.sort()
host_text = ''

for host in host_list:
    if not os.path.isdir("%s/%s" % (rra_dir, host)):
        continue
    host_url = urllib.quote(host)
    host_esc = cgi.escape(host)
    host_text += HOST % {'host_url': host_url, 'host_esc': host_esc}

print HEAD
print
print PAGE % {'hosts': host_text}

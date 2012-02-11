#!/usr/bin/env python

import cgitb
cgitb.enable()

import os
import cgi
import urllib

from nagcat import nagios_objects

HEAD = "Content-Type: text/html"
PAGE = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
    <title>Nagcat/Nagios Trends - Hosts</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <h1>Hosts</h1>
    <table>
    %(groups)s
    </table>
</body>
</html>
"""

GROUP = """
<tr>
    <td class="name"><h3>%(group_esc)s</h3></td>
    <td class="info">%(hosts)s</td>
</tr>
"""

HOST = """
<div class="%(status)s">
    <a href="host.cgi?host=%(host_url)s">%(host_esc)s</a>
    %(status)s - %(output_esc)s
</div>
"""

rra_dir = os.getenv('NAGCAT_RRA_DIR')
obj_file = os.getenv('NAGIOS_OBJECTS')
stat_file = os.getenv('NAGIOS_STATUS')
assert rra_dir and os.path.isdir(rra_dir)
assert obj_file and os.path.isfile(obj_file)
assert stat_file and os.path.isfile(stat_file)

group_list = nagios_objects.ObjectParser(obj_file, ('hostgroup',))['hostgroup']
host_list = nagios_objects.ObjectParser(stat_file, ('host',))['host']

host_map = {}
for host in host_list:
    host_map[host['host_name']] = host

def render_host(host):
    host_url = urllib.quote_plus(host)
    host_esc = cgi.escape(host)
    output_esc = cgi.escape(host_map[host]['plugin_output'])
    status = host_map[host]['current_state']
    if status == '0':
        status = "Up"
    else:
        status = "Down"
    return HOST % {'host_url': host_url, 'host_esc': host_esc,
            'status': status, 'output_esc': output_esc}

ungrouped = set(host_map)
groups = ""
for group in group_list:
    if not group.get('members', None):
        continue
    hosts = ""
    for host in group['members'].split(','):
        ungrouped.discard(host)
        hosts += render_host(host)

    group_esc = cgi.escape(group['alias'])
    groups += GROUP % {'group_esc': group_esc, 'hosts': hosts}

if ungrouped:
    hosts = ""
    for host in sorted(ungrouped):
        hosts += render_host(host)
    groups += GROUP % {'group_esc': "(no group)", 'hosts': hosts}

print HEAD
print
print PAGE % {'groups': groups}

#!/usr/bin/env python

import cgitb
cgitb.enable()

import os
import sys
import cgi

from nagcat.trend import Graph

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

def pull_cgi_data(cgi_store):
    """Pull data from CGI variables, validating the inputs."""
    assert 'host' in cgi_store, "Host parameter not found"
    assert 'rrd' in cgi_store, "RRD parameter not found"
    host = cgi_store.getfirst('host').translate(None, "/.")
    rrd = cgi_store.getfirst('rrd').translate(None, "/.")

    if 'period' in cgi_store:
        period = cgi_store.getfirst('period')
    else:
        period = "day"
    return (host, rrd, period)

### Execution
if __name__ == "__main__":
    cgi_store = cgi.FieldStorage()
    argv_to_cgi(sys.argv, cgi_store)
    (host, rrd, period) = pull_cgi_data(cgi_store)
    path = os.environ.get('NAGCAT_RRA_DIR', None)
    assert os.path.isdir(path), "Invalid NAGCAT_RRA_DIR %s" % path
    graph = Graph(path, host, rrd, period)
    sys.stdout.write("Content-Type: image/png\r\n\r\n%s" % graph.graph())

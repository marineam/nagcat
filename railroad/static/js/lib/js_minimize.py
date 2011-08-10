#!/usr/bin/python

import httplib, urllib, sys

if len(sys.argv) < 2:
    print('Usage: {0} foo.js bar.js ...'.format(sys.argv[0]))
    sys.exit()

js_code = ''
for path in sys.argv[1:]:
    f = open(path)
    js_code += f.read() + '\n'
    f.close()

params = urllib.urlencode([
    ('js_code', js_code),
    ('compilation_level', 'WHITESPACE_ONLY'),
    ('output_format', 'text'),
    ('output_info', 'compiled_code'),
])

headers = {'Content-type': 'application/x-www-form-urlencoded'}
conn = httplib.HTTPConnection('closure-compiler.appspot.com')
conn.request('POST', '/compile', params, headers)
minified = conn.getresponse().read()
print(minified)
conn.close()

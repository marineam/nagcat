# Copyright 2010 ITA Software, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from twisted.trial import unittest
from nagcat import nagios_objects, _object_parser_py

try:
    from nagcat import _object_parser_c
except ImportError:
    _object_parser_c = None


class ModuleTestcase(unittest.TestCase):

    def testObjectParser(self):
        expect = [_object_parser_py.ObjectParser]
        if _object_parser_c:
            expect.append(_object_parser_c.ObjectParser)
        self.assertIn(nagios_objects.ObjectParser, expect)

class ObjectsPyTestCase(unittest.TestCase):

    parser = _object_parser_py.ObjectParser
    status = False

    objects = {
            'host': [
                {
                    'host_name': 'host1',
                    'alias': 'Host 1',
                },
                {
                    'host_name': 'host2',
                    'alias': 'Host 2',
                },
            ],
            'service': [
                {
                    'service_description': "Service 1",
                    'host_name': 'host1',
                },
                {
                    'service_description': "Service 2",
                    'host_name': 'host2',
                },
            ],
        }


    def escape(self, string):
        def cb(match):
            esc = match.group(1)
            if esc == '\\':
                return '\\\\'
            elif esc == '\n':
                return '\\n'
            elif esc == '|':
                return '\\_'
            else:
                assert 0
        return re.sub(r'(\\|\n|\|)', cb, string)

    def mkfile(self, objects):
        file_path = self.mktemp()
        file_obj = open(file_path, 'w')
        for obj_type, seq in objects.iteritems():
            for obj in seq:
                if self.status:
                    file_obj.write("%sstatus {\n" % obj_type)
                else:
                   file_obj.write("define %s {\n" % obj_type)
                for attr, value in obj.iteritems():
                    value = self.escape(value)
                    if self.status:
                        file_obj.write("    %s=%s\n" % (attr, value))
                    else:
                        file_obj.write("    %s %s\n" % (attr, value))
                file_obj.write("    }\n")
        file_obj.close()
        return file_path

    def todict(self, parser):
        return dict((k,parser[k]) for k in parser.types())

    def testSimple(self):
        parser = self.parser(self.mkfile(self.objects))
        parsed = self.todict(parser)
        self.assertEquals(parsed, self.objects)

    def testEscape(self):
        objects = {'host': [{'long_plugin_output': "this\n|\\thing"}],
                   'service': [{'_documentation': "other\n|\\thing"}]}
        parser = self.parser(self.mkfile(objects))
        parsed = self.todict(parser)
        self.assertEquals(parsed, objects)

    def testFilterTypes(self):
        parser = self.parser(self.mkfile(self.objects),
                object_types=('host',))
        parsed = self.todict(parser)
        expect = {'host': self.objects['host']}
        self.assertEquals(parsed, expect)

    def testFilterValues(self):
        parser = self.parser(self.mkfile(self.objects),
                object_select={'host_name': "host1"})
        parsed = self.todict(parser)
        expect = {'host': self.objects['host'][:1],
                'service': self.objects['service'][:1]}
        self.assertEquals(parsed, expect)


class StatusPyTestCase(ObjectsPyTestCase):

    status = True

class ObjectsCTestCase(ObjectsPyTestCase):
    if _object_parser_c:
        parser = _object_parser_c.ObjectParser
    else:
        skip = "C module missing"

class StatusCTestCase(StatusPyTestCase):
    if _object_parser_c:
        parser = _object_parser_c.ObjectParser
    else:
        skip = "C module missing"

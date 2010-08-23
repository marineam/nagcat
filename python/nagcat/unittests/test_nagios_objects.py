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

from twisted.trial import unittest
from nagcat import nagios_objects

class ObjectsTestcase(unittest.TestCase):

    objects = {
            'host': [
                {
                    'host_name': 'host1',
                    'alias': 'Host 1',
                },
            ],
            'service': [
                {
                    'service_description': "Service 1",
                    'host_name': 'host1',
                },
            ],
        }

    def mkfile(self):
        file_path = self.mktemp()
        file_obj = open(file_path, 'w')
        for obj_type, seq in self.objects.iteritems():
            file_obj.write("define %s {\n" % obj_type)
            for obj in seq:
                for attr, value in obj.iteritems():
                    file_obj.write("    %s %s\n" % (attr, value))
            file_obj.write("    }\n")
        file_obj.close()
        return file_path

    def testSimple(self):
        parser = nagios_objects.ObjectParser(self.mkfile())
        parsed = dict((k,parser[k]) for k in parser.types())
        self.assertEquals(parsed, self.objects)

class StatusTestcase(unittest.TestCase):

    objects = {
            'host': [
                {
                    'host_name': 'host1',
                    'alias': 'Host 1',
                },
            ],
            'service': [
                {
                    'service_description': "Service 1",
                    'host_name': 'host1',
                },
            ],
        }

    def mkfile(self):
        file_path = self.mktemp()
        file_obj = open(file_path, 'w')
        for obj_type, seq in self.objects.iteritems():
            file_obj.write("%sstatus {\n" % obj_type)
            for obj in seq:
                for attr, value in obj.iteritems():
                    file_obj.write("    %s=%s\n" % (attr, value))
            file_obj.write("    }\n")
        file_obj.close()
        return file_path

    def testSimple(self):
        parser = nagios_objects.ObjectParser(self.mkfile())
        parsed = dict((k,parser[k]) for k in parser.types())
        self.assertEquals(parsed, self.objects)


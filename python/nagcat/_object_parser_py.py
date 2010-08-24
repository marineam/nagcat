# Copyright 2009 ITA Software, Inc.
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

"""Python parser for nagios object files"""

import re

from nagcat import errors

class ObjectParser(object):
    """Parse a given config file for the requested objects.

    Note that this expects files generated *by* Nagios
    such objects.cache or status.dat
    """

    UNESCAPE = re.compile(r'(\\\\|\\n|\\_)')

    def __init__(self, object_file, object_types=(), object_select=()):
        self._objects = {}

        object_select = dict(object_select)

        try:
            self._parse(object_file, object_types, object_select)
        except IOError, ex:
            raise errors.InitError(
                    "Failed to read Nagios object cache: %s" % ex)

    def _parse(self, object_file, object_types, object_select):

        def unescape(match):
            esc = match.group(1)
            if esc == r'\\':
                return '\\'
            elif esc == r'\n':
                return '\n'
            elif esc == r'\_':
                return '|'
            else:
                assert 0

        for type_ in object_types:
            self._objects[type_] = []

        input = open(object_file)
        splitter = None
        object = None
        object_type = None
        try:
            for line in input:
                line = line.strip()
                if object is None:
                    if line.startswith("define") and line.endswith('{'):
                        type_ = line[7:-2]
                        splitter = None
                    elif line.endswith('status {'):
                        splitter = '='
                        type_ = line[:-8]
                    elif line.endswith(' {'):
                        splitter = '='
                        type_ = line[:-2]
                    else:
                        continue

                    assert type_
                    if object_types and type_ not in object_types:
                        continue
                    object = {}
                    object_type = type_
                elif line == '}':
                    if object_type not in self._objects:
                        self._objects[object_type] = [object]
                    else:
                        self._objects[object_type].append(object)
                    object = None
                    object_type = None
                else:
                    split = line.split(splitter, 1)
                    try:
                        key, value = split
                    except ValueError:
                        key = split[0]
                        value = ""

                    if object_select and key in object_select:
                        selector = object_select[key]
                        if isinstance(selector, basestring):
                            if value != selector:
                                object = None
                                object_type = None
                                continue
                        else:
                            if value not in selector:
                                object = None
                                object_type = None
                                continue

                    if key == "long_plugin_output":
                        value = self.UNESCAPE.sub(unescape, value)
                    object[key] = value
        finally:
            input.close()

    def __getitem__(self, key):
        return self._objects[key]

    def __contains__(self, key):
        return key in self._objects

    def types(self):
        return self._objects.keys()

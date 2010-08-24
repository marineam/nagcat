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

"""Parsers for nagios config and object files"""

import re

from nagcat import errors

try:
    from nagcat._object_parser_c import ObjectParser
except ImportError:
    from nagcat._object_parser_py import ObjectParser

# Make ObjectParser show in pydoc
ObjectParser.__module__ == __name__

class ConfigParser(object):
    """Parser for the main nagios config file (nagios.cfg)"""

    ATTR = re.compile("^(\w+)\s*=\s*(.*)$")
    # Default required config options
    REQUIRED = ('object_cache_file', 'command_file')

    def __init__(self, config_file, required=REQUIRED):
        self._config = {}

        try:
            config_fd = open(config_file)

            for line in config_fd:
                line = line.strip()
                match = self.ATTR.match(line)
                if match:
                    self._config[match.group(1)] = match.group(2)

            config_fd.close()
        except IOError, ex:
            raise errors.InitError("Failed to read Nagios config: %s" % ex)

        for key in required:
            if key not in self._config:
                raise errors.InitError(
                        "Failed to find %s in %s" % (key, config_file))

    def __getitem__(self, key):
        return self._config[key]

    def __contains__(self, key):
        return key in self._config

    def keys(self):
        return self._config.keys()

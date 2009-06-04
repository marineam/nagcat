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

"""Nagios command writer"""

import os
import time

from nagcat import log

class NagiosCommander(object):

    ALLOWED_COMMANDS = {
            'PROCESS_SERVICE_CHECK_RESULT': 4,
            }

    def __init__(self, command_file):
        self._command_file = command_file
        self._command_fd = None
        self._open_command_file()

    def _open_command_file(self):
        try:
            self._command_fd = os.open(self._command_file,
                    os.O_WRONLY | os.O_APPEND | os.O_NONBLOCK)
        except OSError, ex:
            raise errors.InitError("Failed to open command file %s: %s"
                    % (self._command_file, ex))

    def _write_command(self, data):
        try:
            os.write(self._command_fd, data)
        except (OSError, IOError):
            self._open_command_file()
            try:
                os.write(self._command_fd, data)
            except (OSError, IOError), ex:
                raise errors.InitError("Failed to write command to %s: %s"
                        % (self._command_file, ex))

    def command(self, time, cmd, *args):
        """Submit a command to Nagios.

        @param time: a Unix timestamp or None
        @param cmd: a Nagios command name, must be in ALLOWED_COMMANDS
        @param *args: the command arguments
        """
        if not time:
            time = time.time()
        time = int(time)

        assert cmd in self.ALLOWED_COMMANDS
        assert len(args) == self.ALLOWED_COMMANDS[cmd]

        clean_args = [cmd]
        for arg in args[:-1]:
            # These arguments may not contain newlines or ;
            arg = str(arg)
            assert '\n' not in arg and not ';' in arg
            clean_args.append(arg)

        # The last argument may contain newlines but they must be escaped
        # | is not allowed but likely to appear so just replace it
        if args:
            arg = args[-1].replace('\n', '\\n').replace('|', '_')
            clean_args.append(arg)

        formatted = "[%d] %s\n" % (time, ';'.join(clean_args))
        log.trace("Writing Nagios command: %s", formatted)
        self._write_command(formatted)

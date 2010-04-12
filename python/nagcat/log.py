# Copyright 2008-2009 ITA Software, Inc.
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

"""Twisted logging with log levels"""

import os
import sys
import time

from twisted.python import log, logfile, failure, util

# Log levels:
LEVELS = (
        "ERROR", # 0
        "WARN",  # 1
        "INFO",  # 2
        "DEBUG", # 3
        "TRACE", # 4
        )

_logger = None

class TotalLogFile(logfile.LogFile):
    """A log file that can optionally steal stdio"""

    def __init__(self, name, directory, steal_stdio=False, **kwargs):
        self._steal_stdio = steal_stdio
        self._null_fd = os.open("/dev/null", os.O_RDWR)
        logfile.LogFile.__init__(self, name, directory, **kwargs)

    def _do_stdio(self):
        file_fd = self._file.fileno()
        os.dup2(self._null_fd, 0)
        os.dup2(file_fd, 1)
        os.dup2(file_fd, 2)

    def _openFile(self):
        logfile.LogFile._openFile(self)
        if self._steal_stdio:
           self._do_stdio()

    def stdio(self):
        self._steal_stdio = True
        if not self.closed:
            self._do_stdio()

    def close(self):
        os.dup2(self._null_fd, 1)
        os.dup2(self._null_fd, 2)
        logfile.LogFile.close(self)

class LogLevelObserver(object):
    """A file log observer with log levels and rotation"""

    time_format = "%Y-%m-%dT%H:%M:%S %Z"

    def __init__(self, log_name=None, log_level="INFO"):
        assert log_level in LEVELS
        self.log_level = list(LEVELS).index(log_level)
        self.stdio_stolen = False

        if log_name:
            dirname, basename = os.path.split(os.path.abspath(log_name))

            if not os.path.exists(dirname):
                os.makedirs(dirname)

            self.log_file = TotalLogFile(basename, dirname,
                    rotateLength=1024*1024*20, maxRotatedFiles=20)
            self.log_stderr = sys.stderr
        else:
            self.log_file = sys.stdout
            self.log_stderr = None

    def start(self):
        """Setup logging using this observer"""
        log.startLoggingWithObserver(self.emit, setStdout=0)

    def stdio(self):
        """Steal stdout/err and log them"""

        if isinstance(self.log_file, TotalLogFile):
            self.stdio_stolen = True
            self.log_file.stdio()

    def emit(self, event):
        """Twisted log observer event handler"""

        # All exceptions here will normally be lost. Attempt to log
        # any problems to the original stderr in hopes that it is visible
        try:
            if event.get('isError', False):
                level = 0 # ERROR

            # HACK! tcp.Port and udp.Port like to announce themselves
            # loudly but I don't want them to (well UDP at least). This
            # seemed like an easier option than re-implementing things.
            # Also catch all starting/stopping factory noise if it exists.
            elif ('log_level' not in event and 'message' in event and
                    (event['message'][0].startswith(
                        'nagcat.query.NTPProtocol starting on') or
                    (event['message'][0].startswith('(Port ') and
                     event['message'][0].endswith(' Closed)'))) or
                    event['message'][0].startswith('Starting factory') or
                    event['message'][0].startswith('Stopping factory')):
                level = 3 # DEBUG

            else:
                level = event.get('log_level', 2) # INFO

            if self.log_level < level:
                return

            text = log.textFromEventDict(event)
            text = text.replace("\n", "\n    ")
            date = time.strftime(self.time_format,
                    time.localtime(event.get('time', None)))
            line = "%s [%s] %s\n" % (date, LEVELS[level], text)
            util.untilConcludes(self.log_file.write, line)
            util.untilConcludes(self.log_file.flush)

            # During init stderr is used to provide loud errors to the
            # console in addition to the log file to make things obvious.
            if not self.stdio_stolen and level <= 1:
                util.untilConcludes(self.log_stderr.write, line)
                util.untilConcludes(self.log_stderr.flush)
        except:
            if not self.stdio_stolen:
                self.log_stderr.write("%s" % failure.Failure())

def init(log_name, log_level):
    """Initialize the logger (in global scope)"""
    global _logger

    assert _logger is None
    _logger = LogLevelObserver(log_name, log_level)
    _logger.start()

def init_stdio():
    """Signal the logger to steal sys.stdout/err"""
    _logger.stdio()

def _level_factory(index, name):
    """Setup the log level helper functions"""

    def msg(text, *args):
        if _logger and _logger.log_level < index:
            return
        if args:
            text = text % args
        log.msg(text, log_level=index)

    msg.__doc__ = "Log text at level %s" % name
    msg.__name__ = name.lower()
    globals()[msg.__name__] = msg

for index, name in enumerate(LEVELS):
    _level_factory(index, name)
del index, name

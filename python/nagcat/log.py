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

class LogLevelObserver(object):
    """A file log observer with log levels and rotation"""

    time_format = "%Y-%m-%dT%H:%M:%S %Z"

    def __init__(self, log_name=None, log_level="INFO"):
        assert log_level in LEVELS
        self.log_level = list(LEVELS).index(log_level)
        self.log_fallback = sys.stderr

        if log_name:
            dirname, basename = os.path.split(os.path.abspath(log_name))

            if not os.path.exists(dirname):
                os.makedirs(dirname)

            self.log_file = logfile.LogFile(basename, dirname,
                    rotateLength=1024*1024*20, maxRotatedFiles=20)
            self.log_stderr = sys.stderr
        else:
            self.log_file = sys.stdout
            self.log_stderr = None

    def start(self):
        """Setup logging using this observer"""
        log.startLoggingWithObserver(self.emit, setStdout=0)

    def stdio(self, close=False):
        """Steal stdout/err and log them, also optionally close them"""

        if close:
            assert self.log_file != sys.stdin
            sys.stdin.close()
            sys.stdout.close()
            sys.stderr.close()
            os.close(0)
            os.close(1)
            os.close(2)

        self.log_stderr = None
        sys.stdout = log.logfile
        sys.stderr = log.logerr

    def emit(self, event):
        """Twisted log observer event handler"""

        # All exceptions here will normally be lost. Attempt to log
        # any problems to the original stderr in hopes that it is visible
        try:
            if event.get('isError', False):
                level = 0 # ERROR
            else:
                level = event.get('log_level', 2) # INFO

            if self.log_level < level:
                return

            # Use the smarter function if available
            if hasattr(log, 'textFromEventDict'):
                text = log.textFromEventDict(event)
            else:
                text = "\n".join(event['message'])
                if not text:
                    text = str(event.get('failure', ''))

            text = text.replace("\n", "\n    ")
            date = time.strftime(self.time_format,
                    time.localtime(event.get('time', None)))
            line = "%s [%s] %s\n" % (date, LEVELS[level], text)
            util.untilConcludes(self.log_file.write, line)
            util.untilConcludes(self.log_file.flush)

            # During init stderr is used to provide loud errors to the
            # console in addition to the log file to make things obvious.
            if self.log_stderr and level <= 1:
                util.untilConcludes(self.log_stderr.write, line)
                util.untilConcludes(self.log_stderr.flush)
        except:
            self.log_fallback.write("%s" % failure.Failure())

def init(log_name, log_level):
    """Initialize the logger (in global scope)"""
    global _logger

    assert _logger is None
    _logger = LogLevelObserver(log_name, log_level)
    _logger.start()

def init_stdio(close=False):
    """Signal the logger to steal sys.stdout/err"""
    _logger.stdio(close)

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

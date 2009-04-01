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
LEVELS = [ "ERROR", "WARN", "INFO", "DEBUG", "TRACE" ]

class LogLevelObserver(object):
    """A file log observer with log levels and rotation"""

    time_format = "%Y-%m-%dT%H:%M:%S %Z"

    def __init__(self, log_name=None, log_level="INFO"):
        assert log_level in LEVELS
        self.log_level = LEVELS.index(log_level)
        self.log_fallback = sys.stderr

        if log_name:
            dirname, basename = os.path.split(os.path.abspath(log_name))

            if not os.path.exists(dirname):
                os.makedirs(dirname)

            self.log_file = logfile.LogFile(basename, dirname,
                    rotateLength=1024*1024*20, maxRotatedFiles=20)

            # If it already exists and contains data rotate.
            if os.path.getsize(log_name):
                self.log_file.rotate()

            self.log_stderr = sys.stderr
        else:
            self.log_file = sys.stdout
            self.log_stderr = None

    def start(self):
        """Setup logging using this observer"""
        log.startLoggingWithObserver(self.emit, setStdout=0)

    def stdio(self):
        """Steal stdout/err and log them"""
        self.log_stderr = None
        sys.stdout = log.logfile
        sys.stderr = log.logerr

    def emit(self, event):
        """Twisted log observer event handler"""

        # All exceptions here will normally be lost. Attempt to log
        # any problems to the original stderr in hopes that it is visible
        try:
            if event.get('isError', False):
                default = 'ERROR'
            else:
                default = 'INFO'

            level = event.get('log_level', default)

            if level in LEVELS and self.log_level < LEVELS.index(level):
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
            line = "%s [%s] %s\n" % (date, level, text)
            util.untilConcludes(self.log_file.write, line)
            util.untilConcludes(self.log_file.flush)

            # During init stderr is used to provide loud errors to the
            # console in addition to the log file to make things obvious.
            if self.log_stderr and level in ('ERROR', 'WARN'):
                util.untilConcludes(self.log_stderr.write, line)
                util.untilConcludes(self.log_stderr.flush)
        except:
            self.log_fallback.write("%s" % failure.Failure())

def error(text, **kw):
    """Log text at level ERROR"""
    log.msg(text, log_level='ERROR', **kw)

def warn(text, **kw):
    """Log text at level WARN"""
    log.msg(text, log_level='WARN', **kw)

def info(text, **kw):
    """Log text at level INFO"""
    log.msg(text, log_level='INFO', **kw)

def debug(text, **kw):
    """Log text at level DEBUG"""
    log.msg(text, log_level='DEBUG', **kw)

def trace(text, **kw):
    """Log text at level TRACE"""
    log.msg(text, log_level='TRACE', **kw)

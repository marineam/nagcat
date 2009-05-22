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

"""Various Exception classes and friends"""

import sys

from twisted.python import failure
from twisted.python.log import logerr
from coil.errors import StructError

_no_result = object()

class Failure(failure.Failure):
    """Custom failure class to keep the result a callback was given"""

    def __init__(self, exc_value=None, exc_type=None,
            exc_tb=None, result=_no_result):
        self.result = result

        # Don't include the traceback for TestError, processing it
        # has a high overhead and we don't need it for known errors.
        if exc_value is None:
            type_, value, tb = sys.exc_info()
            if type_ in (TestCritical, TestWarning):
                exc_value = value
                exc_type = type_
                exc_tb = None

        failure.Failure.__init__(self, exc_value, exc_type, exc_tb)

    def printTraceback(self, file=None, *args, **kwargs):
        if self.result is not _no_result:
            # Failure is odd and writes to a file like object instead
            # of just returning a string like a sane person would...
            if file is None:
                file = logerr

            file.write("Result given to callback:\n")
            for line in str(self.result).splitlines():
                file.write("    %s\n" % line)

        return failure.Failure.printTraceback(self, file, *args, **kwargs)

def callback(method):
    """Decorator for callback methods to record the result on failure"""

    def catcher(self, result, *args, **kwargs):
        try:
            return method(self, result, *args, **kwargs)
        except:
            if isinstance(result, failure.Failure):
                return Failure()
            else:
                return Failure(result=result)

    return catcher

class TestError(Exception):
    """Records a test failure.

    Use subclasses TestWarning and CriticalError, not this class.
    """

    state = "UNKNOWN"
    index = 3

class TestCritical(TestError):
    state = "CRITICAL"
    index = 2

class TestWarning(TestError):
    state = "WARNING"
    index = 1

class ConfigError(StructError):
    """Error in configuration file."""

class InitError(Exception):
    """Error during startup."""

# Copyright 2008-2010 ITA Software, Inc.
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

"""warning/critical/save filters"""

import re

from zope.interface import classProvides
from twisted.python import failure

from nagcat import errors, filters, util

class SaveFilter(filters._Filter):
    """Save the current result for use in the test report"""

    classProvides(filters.IFilter)

    name = "save"
    handle_default = False

    def __init__(self, test, default, arguments):
        super(SaveFilter, self).__init__(test, default, arguments)

        if not arguments:
            raise errors.InitError("save filters must provide an identifier")

    @errors.callback
    def filter(self, result):
        self.test.saved[self.arguments] = result
        return result

class CriticalFilter(filters._Filter):
    """Mark the test as CRITICAL if the given test fails."""

    classProvides(filters.IFilter)

    name = "critical"
    handle_default = False
    handle_errors = True

    # Supported operators
    ops = ('>','<','=','==','>=','<=','<>','!=','=~','!~')
    # Expression format
    format = re.compile("\s*([<>=!~]{1,2})\s*(\S+.*)")

    # Error to raise, overridden in Filter_warning
    error = errors.TestCritical

    def __init__(self, test, default, arguments):
        super(CriticalFilter, self).__init__(test, default, arguments)

        match = self.format.match(arguments)
        if not match:
            raise errors.InitError("Invalid %s test: %s"
                    % (self.error.state.lower(), arguments))

        self.test_op = match.group(1)
        self.test_val = match.group(2)

        if self.test_op not in self.ops:
            raise errors.InitError("Invalid %s test operator: %s"
                    % (self.error.state.lower(), self.test_op))

        if '~' in self.test_op:
            # Check for a valid regular expression
            try:
                self.test_regex = re.compile(self.test_val, re.MULTILINE)
            except re.error, ex:
                raise errors.InitError("Invalid %s test regex '%s': %s"
                        % (self.error.state.lower(), self.test_val, ex))
        else:
            # not a regular expression, let MathString do its magic.
            self.test_val = util.MathString(self.test_val)
            self.test_regex = None

        # Convert non-python operator
        if self.test_op == '=':
            self.test_op = '=='

    def filter(self, result):
        # Allow critical to override warning
        if (isinstance(result, errors.Failure) and
                isinstance(result.value, errors.TestWarning)):
            true_result = result.result
        elif isinstance(result, failure.Failure):
            return result
        else:
            true_result = result

        # mimic the error.method decorator since we need to
        # report true_result, not result.
        try:
            if self.test_op == '=~':
                if self.test_regex.search(true_result):
                    raise self.error("Matched regex '%s'" % self.test_val)
            elif self.test_op == '!~':
                if not self.test_regex.search(true_result):
                    raise self.error(
                            "Failed to match regex '%s'" % self.test_val)
            else:
                eval_dict = {'a':util.MathString(true_result),
                             'b':self.test_val}

                if eval("a %s b" % self.test_op, eval_dict):
                    raise self.error("Test failed: %s %s"
                            % (self.test_op, self.test_val))
        except Exception:
            result = errors.Failure(result=true_result)

        return result

class WarningFilter(CriticalFilter):
    """Mark the test as WARNING if the given test fails."""

    classProvides(filters.IFilter)

    name = "warning"
    handle_errors = False
    error = errors.TestWarning

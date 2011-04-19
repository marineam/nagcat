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

from zope.interface import classProvides

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

class BaseTestFilter(filters._Filter):
    """Base class for the various test filters"""

    handle_default = False

    raise_error = None
    override_errors = ()

    def __init__(self, test, default, arguments):
        super(BaseTestFilter, self).__init__(test, default, arguments)

        try:
            self.tester = util.Tester.mktest(arguments)
        except util.TesterError, ex:
            raise errors.InitError("Invalid %s test: %s" % (self.name, ex))

        # Only attempt to handle errors if we have something to override
        self.handle_errors = bool(self.override_errors)
        assert self.raise_error

    def filter(self, result):
        if isinstance(result, errors.Failure):
            if isinstance(result.value, self.override_errors):
                true_result = result.result
            else:
                return result
        else:
            true_result = result

        # mimic the error.callback decorator since we need to
        # report true_result, not result.
        try:
            msg = self.tester.test(true_result)
            if msg:
                raise self.raise_error("%s %s" % (self.name, msg))
        except Exception:
            return errors.Failure(result=true_result)
        else:
            return result

class CriticalFilter(BaseTestFilter):
    """Mark the test as CRITICAL if the given test fails."""

    classProvides(filters.IFilter)

    name = "critical"
    raise_error = errors.TestCritical
    override_errors = errors.TestWarning

class WarningFilter(BaseTestFilter):
    """Mark the test as WARNING if the given test fails."""

    classProvides(filters.IFilter)

    name = "warning"
    raise_error = errors.TestWarning

class OKFilter(BaseTestFilter):
    """Short-circuit the test and mark it as OK."""

    classProvides(filters.IFilter)

    name = "ok"
    raise_error = errors.TestOK

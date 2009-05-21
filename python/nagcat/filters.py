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

"""Data filters used by Test objects"""

import re
import time

# Gracefully disable xml/xpath support if not found
try:
    from lxml import etree
except ImportError:
    etree = None

from twisted.python import failure

from nagcat import errors, log, util

# Accept filter specs in the format "name[default]:arguments"
# where [default] and :arguments are optional
_SPEC = re.compile(r'^([a-z][a-z0-9]*)(\[([^\]]*)\])?(:)?')

def Filter(test, spec):
    """Generator that create a Filter class from the spec"""

    assert isinstance(spec, str)

    match = _SPEC.match(spec)
    if not match:
        raise errors.InitError("Invalid filter spec: '%s'" % spec)

    name = match.group(1)
    default = match.group(3)

    if match.group(4):
        arguments = spec[match.end():]
    else:
        arguments = ""

    filter_class = globals().get("Filter_%s" % name, None)
    if filter_class:
        assert issubclass(filter_class, _Filter)
        return filter_class(test, default, arguments)
    else:
        raise errors.InitError("Invalid filter type '%s'" % name)

class _Filter(object):
    """Filter class template"""

    # Set weather this filter allows default values
    handle_default = True
    # Set weather this filter should be on the errorback chain
    # in addition to the normal callback chain.
    handle_errors = False

    def __init__(self, test, default, arguments):
        self.test = test
        self.default = default
        self.arguments = arguments

        if not self.handle_default and self.default is not None:
            raise errors.InitError("'%s' filters cannot take default values"
                    % self.__class__.__name__.replace("Filter_",""))

    @errors.callback
    def filter(self, result):
        """Run the filter on the given input.

        All filters must expect and return a str.
        """
        raise Exception("Unimplemented!")

class Filter_regex(_Filter):
    """Filter data based on a regular expression"""

    def __init__(self, test, default, arguments):
        _Filter.__init__(self, test, default, arguments)
        try:
            self.regex = re.compile(self.arguments, re.MULTILINE | re.DOTALL)
        except re.error, ex:
            raise errors.InitError(
                    "Invalid regex '%s': %s" % (self.arguments, ex))

    @errors.callback
    def filter(self, result):
        log.debug("Matching regex '%s'", self.arguments)

        match = self.regex.search(result)
        if match:
            if match.groups():
                return match.group(1)
            else:
                return match.group(0)
        else:
            if self.default is not None:
                return self.default
            else:
                raise errors.TestCritical(
                        "Failed to match regex '%s'" % self.arguments)

class Filter_date2epoch(_Filter):
    """Transform a string into the time in seconds since epoch"""
    # This filter could use a better name

    def __init__(self, test, default, arguments):
        _Filter.__init__(self, test, default, arguments)

        # Test for bogus patterns
        testing = time.strftime(self.arguments)
        if testing == self.arguments:
            raise errors.InitError("Invalid date format: %s" % self.arguments)

    @errors.callback
    def filter(self, result):
        log.debug("Converting date using format '%s'", self.arguments)

        try:
            return str(time.mktime(time.strptime(result, self.arguments)))
        except ValueError:
            if self.default is not None:
                return self.default
            else:
                raise errors.TestCritical(
                    "Failed to parse date with format '%s'" % self.arguments)

class Filter_xpath(_Filter):
    """Fetch something out of an XML document using XPath."""

    def __init__(self, test, default, arguments):
        _Filter.__init__(self, test, default, arguments)

        if not etree:
            raise errors.InitError("lxml is required for XPath support.")

        try:
            self.xpath = etree.XPath(self.arguments)
        except etree.XPathSyntaxError, ex:
            raise errors.InitError(
                    "Invalid XPath query '%s': %s"  % (self.arguments, ex))

    @errors.callback
    def filter(self, result):
        def format(data):
            if etree.iselement(data):
                ret = etree.tostring(data)
            else:
                ret = str(data)
            return ret.strip()

        log.debug("Fetching XML element %s", self.arguments)

        try:
            root = etree.fromstring(result)
        except etree.XMLSyntaxError, ex:
            raise errors.TestCritical("Invalid XML: %s" % ex)

        data = self.xpath(root)

        if isinstance(data, list) and data:
            return "\n".join([format(x) for x in data])
        elif isinstance(data, list):
            if self.default is not None:
                return self.default
            else:
                raise errors.TestCritical(
                        "Failed to find xml element %s" % self.arguments)
        else:
            return format(data)

class Filter_save(_Filter):
    """Save the current result for use in the test report"""

    handle_default = False
    handle_errors = True

    def __init__(self, test, default, arguments):
        _Filter.__init__(self, test, default, arguments)

        if not arguments:
            raise errors.InitError("save filters must provide an identifier")

    @errors.callback
    def filter(self, result):
        # Pull the value out of the error if needed
        if isinstance(result, failure.Failure):
            if isinstance(result, errors.Failure):
                value = result.result
            else:
                value = None
        else:
            value = result

        self.test.saved[self.arguments] = value

        return result

class Filter_critical(_Filter):
    """Mark the test as CRITICAL if the given test fails."""

    handle_default = False
    handle_errors = True

    # Supported operators
    ops = ('>','<','=','==','>=','<=','<>','!=','=~','!~')
    # Expression format
    format = re.compile("\s*([<>=!~]{1,2})\s*(\S+.*)")

    # Error to raise, overridden in Filter_warning
    error = errors.TestCritical

    def __init__(self, test, default, arguments):
        _Filter.__init__(self, test, default, arguments)

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
                    raise self.error(
                            "Failed to match regex '%s'" % self.test_val)
            elif self.test_op == '!~':
                if not self.test_regex.search(true_result):
                    raise self.error("Matched regex '%s'" % self.test_val)
            else:
                eval_dict = {'a':util.MathString(true_result),
                             'b':self.test_val}

                if eval("a %s b" % self.test_op, eval_dict):
                    raise self.error("Test failed: %s %s"
                            % (self.test_op, self.test_val))
        except Exception, ex:
            result = errors.Failure(result=true_result)

        return result

class Filter_warning(Filter_critical):
    """Mark the test as WARNING if the given test fails."""

    handle_errors = False
    error = errors.TestWarning


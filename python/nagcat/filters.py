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

from nagcat import util, log

# Accept filter specs in the format "name[default]:arguments"
# where [default] and :arguments are optional
_SPEC = re.compile(r'^([a-z][a-z0-9]*)(\[([^\]]*)\])?(:)?')

def Filter(test, spec):
    """Generator that create a Filter class from the spec"""

    assert isinstance(spec, str)

    match = _SPEC.match(spec)
    if not match:
        raise util.KnownError("Invalid filter spec: %s" % repr(spec))

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
        raise util.KnownError("Invalid filter type %s" % repr(name))

class _Filter(object):
    """Filter class template"""

    def __init__(self, test, default, arguments):
        self.test = test
        self.default = default
        self.arguments = arguments

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
            raise util.KnownError("Invalid regex %s: %s"
                    % (repr(self.arguments), ex))

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
                raise util.KnownError("Failed to match regex %s"
                        % repr(self.arguments), result, "CRITICAL")

class Filter_date2epoch(_Filter):
    """Transform a string into the time in seconds since epoch"""
    # This filter could use a better name

    def __init__(self, test, default, arguments):
        _Filter.__init__(self, test, default, arguments)

        # Test for bogus patterns
        testing = time.strftime(self.arguments)
        if testing == self.arguments:
            raise util.KnownError("Invalid date format: %s" % self.arguments)

    def filter(self, result):
        log.debug("Converting date using format '%s'", self.arguments)

        try:
            return str(time.mktime(time.strptime(result, self.arguments)))
        except ValueError:
            if self.default is not None:
                return self.default
            else:
               raise util.KnownError("Failed to parse date with format '%s'"
                       % self.arguments, result, "CRITICAL")

class Filter_xpath(_Filter):
    """Fetch something out of an XML document using XPath."""

    def __init__(self, test, default, arguments):
        _Filter.__init__(self, test, default, arguments)

        if not etree:
            raise util.KnownError("XPath support requires lxml!")

        try:
            self.xpath = etree.XPath(self.arguments)
        except etree.XPathSyntaxError, ex:
            raise util.KnownError("Invalid XPath query %s: %s"
                    % (repr(self.arguments), ex))

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
            raise util.KnownError("Invalid XML", result, "CRITICAL", ex)

        data = self.xpath(root)

        if isinstance(data, list) and data:
            return "\n".join([format(x) for x in data])
        elif isinstance(data, list):
            if self.default is not None:
                return self.default
            else:
                raise util.KnownError("Failed to find xml element %s"
                        % repr(self.arguments), result, "CRITICAL")
        else:
            return format(data)

class Filter_save(_Filter):
    """Save the current result for use in the test report"""

    def __init__(self, test, default, arguments):
        _Filter.__init__(self, test, default, arguments)

        if self.default is not None:
            raise util.KnownError("'save' filters cannot take default values")

    def filter(self, result):
        self.test.saved.setdefault(self.arguments, result)
        return result

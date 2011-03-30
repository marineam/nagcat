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

"""Regular Expression Filter"""

import re
from zope.interface import classProvides
from nagcat import errors, filters, log

class RegexFilter(filters._Filter):
    """Filter data based on a regular expression"""

    classProvides(filters.IFilter)

    name = "regex"

    def __init__(self, test, default, arguments):
        super(RegexFilter, self).__init__(test, default, arguments)
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
        elif self.default is not None:
            return self.default
        else:
            raise errors.TestCritical(
                    "Failed to match regex '%s'" % self.arguments)

class GrepFilter(filters._Filter):
    """Grep data based on a regular expression"""

    classProvides(filters.IFilter)

    name = "grep"
    invert = False

    def __init__(self, test, default, arguments):
        super(GrepFilter, self).__init__(test, default, arguments)
        try:
            self.regex = re.compile(self.arguments)
        except re.error, ex:
            raise errors.InitError(
                    "Invalid regex '%s': %s" % (self.arguments, ex))

    @errors.callback
    def filter(self, result):
        log.debug("Grepping regex '%s'", self.arguments)

        output = ""
        for line in result.splitlines(True):
            if self.regex.search(line):
                if not self.invert:
                    output += line
            else:
                if self.invert:
                    output += line

        if output:
            return output
        elif self.default is not None:
            return self.default
        else:
            raise errors.TestCritical(
                    "Failed to match regex '%s'" % self.arguments)

class GrepVFilter(GrepFilter):
    classProvides(filters.IFilter)
    name = "grepv"
    invert = True

class LinesFilter(filters._Filter):
    """Report the number of lines, similar to wc -l

    Note: Unlike wc -l we always act as if there is a terminating newline
    whether it is there or not. Thus "foo" and "foo\n" are both one line.
    Only an empty string counts as zero lines.
    """

    classProvides(filters.IFilter)

    name = "lines"
    handle_default = False
    handle_arguments = False

    @errors.callback
    def filter(self, result):
        if not result:
            return "0"
        # strip a single terminating newline
        if result.endswith('\n'):
            result = result[:-1]
        return str(len(result.split('\n')))

class BytesFilter(filters._Filter):
    """Report the number of bites, like wc -c

    Unlike the lines filter I don't fiddle with newlines here.
    """

    classProvides(filters.IFilter)

    name = "bytes"
    handle_default = False
    handle_arguments = False

    @errors.callback
    def filter(self, result):
        return str(len(result))

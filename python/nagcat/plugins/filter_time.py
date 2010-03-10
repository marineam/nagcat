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

"""Date/Time Filters"""

import time
from zope.interface import classProvides
from nagcat import errors, filters, log

class DateFilter(filters._Filter):
    """Transform a string into the time in seconds since epoch"""

    classProvides(filters.IFilter)

    # This filter could use a better name
    name = "date2epoch"

    def __init__(self, test, default, arguments):
        super(DateFilter, self).__init__(test, default, arguments)

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

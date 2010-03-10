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

"""XML Filters"""

# Gracefully disable xml/xpath support if not found
try:
    from lxml import etree
except ImportError:
    etree = None

from zope.interface import classProvides
from nagcat import errors, filters, log

class XPathFilter(filters._Filter):
    """Fetch something out of an XML document using XPath."""

    classProvides(filters.IFilter)

    name = "xpath"

    def __init__(self, test, default, arguments):
        super(XPathFilter, self).__init__(test, default, arguments)

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

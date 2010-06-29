# Copyright 2010 ITA Software, Inc.
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

"""RRDTool Queries"""

import time

from zope.interface import classProvides
from twisted.internet import defer
from nagcat import errors, query, util

try:
    from lxml import etree
except ImportError:
    etree = None

try:
    import twirrdy
except ImportError:
    twirrdy = None

class LastUpdateQuery(query.Query):
    """Fetch the latest update for a specific service"""

    classProvides(query.IQuery)

    name = "rrd_lastupdate"

    def __init__(self, nagcat, conf):
        if not nagcat.trend:
            raise errors.InitError("rrdtool support is disabled")

        super(LastUpdateQuery, self).__init__(nagcat, conf)
        self._nagcat = nagcat
        self.conf['host'] = conf['host']
        self.conf['description'] = conf['description']
        self.conf['freshness'] = util.Interval(conf.get('freshness', None))
        self.conf['source'] = conf.get('source', None)
        if not self.conf['source'] and not etree:
            raise errors.InitError("lxml is required")

    def _start(self):
        deferred = self._nagcat.trend.lastupdate(
                self.conf['host'], self.conf['description'])
        if self.conf['freshness']:
            deferred.addCallback(self._freshness)
        if self.conf['source']:
            deferred.addCallback(self._filter)
        else:
            deferred.addCallback(self._format)
        return deferred

    @errors.callback
    def _errors(self, failure):
        if isinstance(falure.value, twirrdy.RRDToolError):
            raise errors.TestCritical(str(failure.value))
        else:
            return failure

    @errors.callback
    def _freshness(self, result):
        now = time.time()
        if result[0] + self.conf['freshness'] < now:
            raise errors.TestCritical("Stale RRD data. "
                    "Last update %s seconds ago" % (now - result[0]))
        else:
            return result

    @errors.callback
    def _filter(self, result):
        if self.conf['source'] not in result[1]:
            raise errors.TestCritical("Invalid data source %r" %
                                     self.conf['source'])
        value = result[1][self.conf['source']]
        if value is None:
            return ''
        else:
            return str(value)

    @errors.callback
    def _format(self, result):
        root = etree.Element('rrd')
        etree.SubElement(root, 'lastupdate').text = str(result[0])
        for name, last in result[1].iteritems():
            ds = etree.SubElement(root, 'ds')
            etree.SubElement(ds, 'name').text = name
            if last is None:
                last = ''
            etree.SubElement(ds, 'last_ds').text = str(last)
        return etree.tostring(root, pretty_print=True)

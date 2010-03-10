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

"""Query and friends.

All requests are defined as a Query class which is a Runnable.
"""

import errno

from twisted.internet import defer
from twisted.internet import error as neterror

from nagcat import errors, filters, log, plugin, scheduler

_queries = {}

def addQuery(conf, qcls=None):
    """Create a new query and register it or return an existing one"""

    # Find the correct Query class for this type
    if not qcls:
        qtype = conf.get('type')
        qcls = plugin.search(IQuery, qtype, None)
        if not qcls:
            raise errors.ConfigError(conf, "Unknown query type '%s'" % qtype)

    qobj = qcls(conf)
    key = str(qobj)
    if key in _queries:
        log.debug("Reusing query '%s'", key)
        qobj = _queries[key]
        qobj.update(conf)
    else:
        log.debug("Adding query '%s'", key)
        _queries[key] = qobj

    return qobj

class IQuery(plugin.INagcatPlugin):
    """Interface for finding Query plugin classes"""

class Query(scheduler.Runnable):
    """Query objects make a single request or run a single process as
    defined in its configuration. The only state they may contain when
    it is not running is the results from the last run (be it real data
    or a Failure object).

    All state that defines a query *MUST* be saved on self.conf and
    never changed after __init__ to allow identical queries to be
    identified reliably.

    Query objects are only used by SimpleTest objects.
    """

    def __init__(self, conf):
        scheduler.Runnable.__init__(self, conf)

        # self.conf must contain all configuration variables that
        # this object uses so identical Queries can be identified.
        self.conf = {}

        # Used by queries that can send a unique request id,
        # currently only HTTP...
        self.request_id = None

        # Used by HTTP queries to report a user-friendly url
        self.request_url = None

        # All queries should handle timeouts
        try:
            self.conf['timeout'] = float(conf.get('timeout', 15))
        except ValueError:
            raise errors.ConfigError(conf,
                    "Invalid timeout value '%s'" % conf.get('timeout'))

        if self.conf['timeout'] <= 0:
            raise errors.ConfigError(conf,
                    "Invalid timeout value '%s'" % conf.get('timeout'))

    @errors.callback
    def _failure_tcp(self, result):
        """Catch common TCP failures and convert them to a TestError"""

        if isinstance(result.value, neterror.TimeoutError):
            raise errors.TestCritical("TCP handshake timeout")

        elif isinstance(result.value, neterror.ConnectionRefusedError):
            raise errors.TestCritical("TCP connection refused")

        elif isinstance(result.value, neterror.ConnectionLost):
            raise errors.TestCritical("TCP connection lost unexpectedly")

        elif isinstance(result.value, neterror.ConnectError):
            if result.value.osError == errno.EMFILE:
                log.error("Too many open files! Restart with a new ulimit -n")
                raise errors.TestAbort("NAGCAT ERROR: %s" % result.value)
            raise errors.TestCritical("TCP error: %s" % result.value)

        return result

    def __str__(self):
        return "<%s %r>" % (self.__class__.__name__, self.conf)

    def update(self, conf):
        """ Update a reused Query object.

        When a query object is reused for a new query it will be given
        the new query's config via this method. Most fo the time this will
        not need to be used but may be useful for the tricky cases.
        """
        pass

class FilteredQuery(Query):
    """A query that wraps another query and applies filters to it"""

    def __init__(self, conf):
        Query.__init__(self, conf)

        self._port = conf.get('port', None)
        # Used by the save filter and report
        self.saved = {}

        # Create the filter objects
        filter_list = conf.get('filters', [])
        self._filters = [filters.Filter(self, x) for x in filter_list]

        # Add final critical and warning tests
        if 'critical' in conf:
            self._filters.append(filters.get_filter(
                self, 'critical', None, conf['critical']))
        if 'warning' in conf:
            self._filters.append(filters.get_filter(
                self, 'warning', None, conf['warning']))

        self._query = addQuery(conf)
        self.addDependency(self._query)

    def _start(self):
        self.saved.clear()
        # Save the request id and url so it will appear in reports
        if self._query.request_id:
            self.saved['Request ID'] = self._query.request_id
        if self._query.request_url:
            self.saved['Request URL'] = self._query.request_url

        deferred = defer.Deferred()
        deferred.callback(self._query.result)

        for filter in self._filters:
            if filter.handle_errors:
                deferred.addBoth(filter.filter)
            else:
                deferred.addCallback(filter.filter)

        return deferred

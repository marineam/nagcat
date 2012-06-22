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

from twisted.internet import defer, reactor
from twisted.internet import error as neterror

try:
    from OpenSSL import SSL, crypto
    from twisted.internet import ssl
except ImportError:
    SSL = None

from nagcat import errors, filters, log, plugin, runnable, util

class QueryManager(object):

    def __init__(self, nagcat):
        self._nagcat = nagcat
        self._queries = {}

    def new_query(self, conf, qcls=None):
        """Create a new query and register it or return an existing one"""

        # Find the correct Query class for this type
        if not qcls:
            qtype = conf.get('type')
            qcls = plugin.search(IQuery, qtype, None)
            if not qcls:
                raise errors.ConfigError(conf,
                        "Unknown query type '%s'" % qtype)

        qobj = qcls(self._nagcat, conf)
        key = str(qobj)
        if key in self._queries:
            log.debug("Reusing query '%s'", key)
            qobj = self._queries[key]
            qobj.update(conf)
        else:
            log.debug("Adding query '%s'", key)
            self._queries[key] = qobj

        return qobj

class IQuery(plugin.INagcatPlugin):
    """Interface for finding Query plugin classes"""

class Query(runnable.Runnable):
    """Query objects make a single request or run a single process as
    defined in its configuration. The only state they may contain when
    it is not running is the results from the last run (be it real data
    or a Failure object).

    All state that defines a query *MUST* be saved on self.conf and
    never changed after __init__ to allow identical queries to be
    identified reliably.

    Query objects are only used by SimpleTest objects.
    """

    type = "Query"

    def __init__(self, nagcat, conf):
        super(Query, self).__init__(conf)

        # self.conf must contain all configuration variables that
        # this object uses so identical Queries can be identified.
        self.conf = {}

        # Used by the save filter and by queries to report any
        # extra pieces of metadata such as Request ID/URL.
        self.saved = {}

        # Semi-fatal init errors, forces query to UNKNOWN
        self.init_errors = []

        # All queries should handle timeouts
        try:
            interval = util.Interval(
                conf.get('timeout', nagcat.default_timeout))
            self.conf['timeout'] = interval.seconds
        except util.IntervalError, ex:
            raise errors.ConfigError(conf, "Invalid timeout: %s" % ex)

        if self.conf['timeout'] <= 0:
            raise errors.ConfigError(conf,
                    "Invalid timeout value '%s'" % conf.get('timeout'))

    def _start_self(self):
        self.saved.clear()
        if self.init_errors:
            msg = '\n'.join(self.init_errors)
            return defer.fail(errors.Failure(errors.TestUnknown(msg)))
        else:
            return super(Query, self)._start_self()

    @errors.callback
    def _failure_tcp(self, result):
        """Catch common TCP failures and convert them to a TestError"""

        if isinstance(result.value, neterror.TimeoutError):
            raise errors.TestCritical("TCP Error: handshake timeout")

        elif isinstance(result.value, neterror.ConnectionRefusedError):
            raise errors.TestCritical("TCP Error: connection refused")

        elif isinstance(result.value, neterror.ConnectionLost):
            raise errors.TestCritical("TCP Error: connection lost " \
                                      "unexpectedly")

        elif isinstance(result.value, neterror.ConnectError):
            if result.value.osError == errno.EMFILE:
                log.error("Too many open files! Restart with a new ulimit -n")
                raise errors.TestAbort("NAGCAT ERROR: %s" % result.value)
            raise errors.TestCritical("TCP Error: %s" % result.value)

        return result

    def _connect(self, factory):
        # Split out the reactor.connect call to allow for easy
        # overriding in SSLMixin for adding SSL support.
        reactor.connectTCP(self.addr, self.conf['port'],
                factory, self.conf['timeout'])

    def __str__(self):
        return "<%s %r>" % (self.__class__.__name__, self.conf)

    def update(self, conf):
        """Update a reused Query object.

        When a query object is reused for a new query it will be given
        the new query's config via this method. In most cases all we
        need to do is select the lower of the two repeat values.
        """
        try:
            repeat = util.Interval(conf.get('repeat', '1m'))
        except util.IntervalError, ex:
            raise errors.ConfigError(conf, "Invalid repeat: %s" % ex)

        if self.repeat < repeat:
            self.repeat = repeat


class SSLMixin(Query):
    """Mixin class for adding SSL support to a query.

    Note that subclasses must set self.conf['port']

    Example usage:
    >>>    class HTTPS(SSLMixin, HTTP):
    >>>        pass
    """

    def __init__(self, nagcat, conf):
        super(SSLMixin, self).__init__(nagcat, conf)
        if SSL is None:
            raise errors.InitError("pyOpenSSL is required for SSL support.")

        for opt in ('key', 'cert', 'cacert'):
            self.conf['ssl_'+opt] = conf.get('ssl_'+opt, None)
            key_type = str(conf.get('ssl_'+opt+'_type', ''))
            if not key_type or key_type.upper() == "PEM":
                key_type = crypto.FILETYPE_PEM
            elif key_type.upper() == "ASN1":
                key_type = crypto.FILETYPE_ASN1
            else:
                raise errors.InitError("Invalid ssl_%s_type %r, "
                        "must be 'PEM' or 'ASN1'" % (opt, key_type))
            self.conf['ssl_%s_type'%opt] = key_type

        def maybe_read(key, private=False):
            filetype = self.conf[key+'_type']
            path = self.conf[key]
            if not path:
                return None

            log.debug("Loading %s from %s", key, path)

            try:
                fd = open(path)
                try:
                    data = fd.read()
                finally:
                    fd.close()
            except IOError, ex:
                self.init_errors.append("Failed to read %s file %s: %s" %
                                        (key, path, ex.strerror))
                return None

            log.trace("Loaded %s:\n%s", key, data)

            if private:
                return crypto.load_privatekey(filetype, data)
            else:
                return crypto.load_certificate(filetype, data)

        cacert = maybe_read('ssl_cacert')
        if cacert:
            cacert = [cacert]

        # Only use both if we can load both
        key = maybe_read('ssl_key', private=True)
        cert = maybe_read('ssl_cert')
        if not (key and cert):
            key, cert = None, None

        self.context = ssl.CertificateOptions(
                privateKey=key, certificate=cert, caCerts=cacert,
                verify=bool(cacert), method=SSL.SSLv23_METHOD)
        # Use SSLv23 to support v3 and TLSv1 but disable v2 (below)
        sslcontext = self.context.getContext()
        sslcontext.set_options(SSL.OP_NO_SSLv2)

    @errors.callback
    def _failure_tcp(self, result):
        """Also catch SSL errors"""

        result = super(SSLMixin, self)._failure_tcp(result)

        if isinstance(result.value, SSL.Error):
            raise errors.TestCritical("SSL Error: %s" % result.value)

        return result

    def _connect(self, factory):
        reactor.connectSSL(self.addr, self.conf['port'],
                factory, self.context, self.conf['timeout'])

class FilteredQuery(Query):
    """A query that wraps another query and applies filters to it"""

    # For the scheduler stats
    name = "filter"

    def __init__(self, nagcat, conf):
        super(FilteredQuery, self).__init__(nagcat, conf)

        # Create the filter objects
        filter_list = conf.get('filters', [])
        for check in ('critical', 'warning',
                      'expectcritical', 'expectwarning', 'expecterror'):
            expr = conf.get(check, None)
            if expr:
                filter_list.append("%s:%s" % (check, expr))

        self._filters = [filters.Filter(self, x) for x in filter_list]
        self._query = nagcat.new_query(conf)
        self.conf['filters'] = str(filter_list)
        self.conf['query'] = str(self._query)
        self.addDependency(self._query)

    def _start(self):
        self.saved.update(self._query.saved)

        deferred = defer.Deferred()
        deferred.callback(self._query.result)

        for filter in self._filters:
            if filter.handle_errors:
                deferred.addBoth(filter.filter)
            else:
                deferred.addCallback(filter.filter)

        return deferred

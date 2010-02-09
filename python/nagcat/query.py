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

import os
import re
import errno
import signal
import struct
import urlparse
from base64 import b64encode

try:
    import uuid
except ImportError:
    uuid = None

from twisted.internet import reactor, defer, protocol, process, threads
from twisted.internet import error as neterror
from twisted.web import error as weberror
from twisted.web.client import HTTPClientFactory
from twisted.python.util import InsensitiveDict
from twisted.python import failure
from twisted.enterprise import adbapi

# SSL support is screwy
try:
   from twisted.internet import ssl
except ImportError:
   # happens the first time the interpreter tries to import it
   ssl = None
if ssl and not ssl.supported:
   # happens second and later times
   ssl = None

try:
    from lxml import etree
except ImportError:
    etree = None

try:
    import cx_Oracle
except ImportError:
    cx_Oracle = None

from snapy import netsnmp
from snapy.twisted import Session as SnmpSession

from nagcat import errors, log, scheduler

_queries = {}

def addQuery(conf, qcls=None):
    """Create a new query and register it or return an existing one"""

    # Find the correct Query class for this type
    if not qcls:
        qtype = conf.get('type')
        qcls = globals().get('Query_%s' % qtype, None)
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

class Query_noop(Query):
    """Dummy query useful for testing."""

    def __init__(self, conf):
        Query.__init__(self, conf)
        self.conf['data'] = conf.get('data', None)

    def _start(self):
        return defer.succeed(self.conf['data'])

class Query_http(Query):
    """Process an HTTP GET or POST"""

    scheme = "http"
    port = 80

    def __init__(self, conf):
        Query.__init__(self, conf)

        self.agent = "NagCat" # Add more info?
        self.conf['addr'] = self.addr
        self.conf['port'] = int(conf.get('port', self.port))
        self.conf['path'] = conf.get('path', '/')
        self.conf['data'] = conf.get('data', None)
        headers = conf.get('headers', {})

        # Some versions of twisted will send Host twice if it is in the
        # headers dict. Instead we set factory.host.
        if self.conf['port'] == self.port:
            self.headers_host = self.host
        else:
            self.headers_host = "%s:%s" % (self.host, self.conf['port'])

        # We need to make sure headers is a dict.
        self.headers = InsensitiveDict()
        for (key, val) in headers.iteritems():
            if key.lower() == 'host':
                self.headers_host = val
            else:
                self.headers[key] = val

        # Set the Authorization header if user/pass are provided
        user = conf.get('username', None)
        if user is not None:
            auth = b64encode("%s:%s" % (user, conf['password']))
            self.headers['Authorization'] = "Basic %s" % auth

        # Also convert to a lower-case only dict for self.conf so
        # that queries that differ only by case are still shared.
        self.conf['headers'] = InsensitiveDict(preserve=0)
        self.conf['headers']['host'] = self.headers_host
        self.conf['headers'].update(self.headers)

        if self.conf['data']:
            self.method = "POST"
        else:
            self.method = "GET"

        self.request_url = urlparse.urlunsplit((self.scheme,
                self.headers_host, self.conf['path'], None, None))

    def _start(self):
        # Generate a request id if possible
        if uuid:
            self.request_id = str(uuid.uuid1())
            self.headers['X-Request-Id'] = self.request_id

        factory = HTTPClientFactory(url=self.conf['path'],
                method=self.method, postdata=self.conf['data'],
                headers=self.headers, agent=self.agent,
                timeout=self.conf['timeout'], followRedirect=0)
        factory.host = self.headers_host
        factory.noisy = False
        factory.deferred.addErrback(self._failure_tcp)
        factory.deferred.addErrback(self._failure_http)
        self._connect(factory)
        return factory.deferred

    @errors.callback
    def _failure_http(self, result):
        """Convert HTTP specific failures to a TestError"""

        if isinstance(result.value, defer.TimeoutError):
            raise errors.TestCritical("Timeout waiting on HTTP response")

        elif isinstance(result.value, neterror.ConnectionDone):
            raise errors.TestCritical("Empty HTTP Response")

        elif isinstance(result.value, weberror.PageRedirect):
            # Redirects aren't actually an error :-)
            result = "%s\n%s" % (result.value, result.value.location)

        elif isinstance(result.value, weberror.Error):
            raise errors.TestCritical("HTTP error: %s" % result.value)

        return result

    def _connect(self, factory):
        # Split out the reactor.connect call to allow for easy
        # overriding in HTTPSQuery
        reactor.connectTCP(self.addr, self.conf['port'],
                factory, self.conf['timeout'])


class Query_https(Query_http):
    """Process an HTTP GET or POST over SSL"""

    scheme = "https"
    port = 443

    def __init__(self, conf):
        if ssl is None:
            raise errors.InitError("pyOpenSSL is required for HTTPS support.")
        Query_http.__init__(self, conf)

    def _connect(self, factory):
        context = ssl.ClientContextFactory()
        reactor.connectSSL(self.addr, self.conf['port'],
                factory, context, self.conf['timeout'])

class RawProtocol(protocol.Protocol):
    """Basic protocol handler for raw TCP/SSL queries.

    This and its factory are modeled after the twisted.web HTTP client.
    """

    expected_loss = False

    def connectionMade(self):
        self.result = ""
        self.timedout = False
        if self.factory.conf['data']:
            self.transport.write(self.factory.conf['data'])
        self.transport.loseWriteConnection()

    def dataReceived(self, data):
        self.result += data

    def timeout(self):
        self.timedout = True
        self.transport.loseConnection()

    def connectionLost(self, reason):
        if self.timedout:
            self.factory.result(errors.Failure(
                errors.TestCritical("Timeout waiting for connection close."),
                result=self.result))
        elif self.result:
            self.factory.result(self.result)
        else:
            self.factory.result(reason)

class RawFactory(protocol.ClientFactory):
    """Handle raw TCP/SSL queries"""

    noisy = False
    protocol = RawProtocol

    def __init__(self, conf):
        self.conf = conf
        self.deferred = defer.Deferred()

    def buildProtocol(self, addr):
        # Setup timeout callback
        proto = protocol.ClientFactory.buildProtocol(self, addr)

        call_id = reactor.callLater(self.conf['timeout'], proto.timeout)
        self.deferred.addBoth(self._cancelTimeout, call_id)

        return proto

    def _cancelTimeout(self, result, call_id):
        if call_id.active():
            call_id.cancel()
        return result

    def clientConnectionFailed(self, connector, reason):
        self.result(reason)

    def result(self, result):
        self.deferred.callback(result)

class Query_tcp(Query):
    """Send and receive data over a raw TCP socket"""

    def __init__(self, conf):
        Query.__init__(self, conf)

        self.conf['addr'] = self.addr
        self.conf['port'] = int(conf.get('port'))
        self.conf['data'] = conf.get('data', None)

    def _start(self):
        factory = RawFactory(self.conf)
        factory.deferred.addErrback(self._failure_tcp)
        self._connect(factory)
        return factory.deferred

    def _connect(self, factory):
        reactor.connectTCP(self.addr, self.conf['port'],
                factory, self.conf['timeout'])

class Query_ssl(Query_tcp):
    """Send and receive data over a raw SSL socket"""

    def __init__(self, conf):
        if ssl is None:
            raise errors.InitError("pyOpenSSL is required for SSL support.")
        Query_tcp.__init__(self, conf)

    def _connect(self, factory):
        context = ssl.ClientContextFactory()
        reactor.connectSSL(self.addr, self.conf['port'],
                factory, context, self.conf['timeout'])

class SubprocessProtocol(protocol.ProcessProtocol):
    """Handle input/output for subprocess queries"""

    timedout = False

    def connectionMade(self):
        self.result = ""
        if self.factory.conf['data']:
            self.transport.write(self.factory.conf['data'])
        self.transport.closeStdin()

    def outReceived(self, data):
        self.result += data

    def timeout(self):
        self.timedout = True
        self.transport.loseConnection()
        # Kill all processes in the child's process group
        try:
            os.kill(-int(self.transport.pid), signal.SIGTERM)
        except OSError, ex:
            log.warn("Failed to send TERM to a subprocess: %s", ex)

    def processEnded(self, reason):
        if isinstance(reason.value, neterror.ProcessDone):
            result = self.result
        elif isinstance(reason.value, neterror.ProcessTerminated):
            if self.timedout:
                result = errors.Failure(errors.TestCritical(
                    "Timeout waiting for command to finish."),
                    result=self.result)
            elif reason.value.exitCode == 127:
                result = errors.Failure(errors.TestCritical(
                    "Command not found."))
            else:
                result = errors.Failure(errors.TestCritical(
                    reason.value.args[0]), result=self.result)
        else:
            result = reason

        self.factory.result(result)

class SubprocessFactory(process.Process):
    """Execute a subprocess"""

    def __init__(self, conf):
        self.conf = conf
        self.deferred = defer.Deferred()
        self._startProcess(("/bin/sh", "-c", conf['command']))

    def _startProcess(self, command):
        command = [str(x) for x in command]
        log.debug("Running process: %s", command)

        proto = SubprocessProtocol()
        proto.factory = self

        # Setup timeout
        call_id = reactor.callLater(self.conf['timeout'], proto.timeout)
        self.deferred.addBoth(self._cancelTimeout, call_id)

        # Setup shutdown cleanup
        call_id = reactor.addSystemEventTrigger('after', 'shutdown',
                proto.timeout)
        self.deferred.addBoth(self._cancelCleanup, call_id)

        process.Process.__init__(self, reactor, command[0], command,
                self.conf['environment'], path=None, proto=proto)

    def result(self, result):
        self.deferred.callback(result)

    def _cancelTimeout(self, result, call_id):
        if call_id.active():
            call_id.cancel()
        return result

    def _cancelCleanup(self, result, call_id):
        reactor.removeSystemEventTrigger(call_id)
        return result

    def _setupChild(self, *args, **kwargs):
        # called in the child fork, set new process group
        os.setpgrp()
        process.Process._setupChild(self, *args, **kwargs)


class Query_subprocess(Query):
    def __init__(self, conf):
        Query.__init__(self, conf)

        env = os.environ.copy()
        if 'environment' in conf:
            env.update(conf['environment'])

        self.conf['command'] = conf['command']
        self.conf['data'] = conf.get('data', "")
        self.conf['environment'] = env

    def _start(self):
        proc = SubprocessFactory(self.conf)
        return proc.deferred


class _Query_snmp_common(Query):
    """Parent class for both Query_snmp and QuerySnmp_combined."""

    def __init__(self, conf):
        Query.__init__(self, conf)

        protocol = conf.get('protocol', 'udp')
        if protocol not in ('udp', 'tcp', 'unix'):
            raise errors.ConfigError(conf,
                    "Invalid SNMP protocol: %r" % conf['protocol'])

        # Unix sockets are used by the unit tests
        if protocol == 'unix':
            self.conf['addr'] = 'unix:%s' % conf['path']
        else:
            self.conf['addr'] = '%s:%s:%d' % (protocol,
                    self.addr, int(conf.get('port', 161)))

        self.conf['version'] = str(conf.get('version', '2c'))
        if self.conf['version'] not in ('1', '2c'):
            raise errors.ConfigError(conf,
                    "Invalid SNMP version %r" % conf['version'])

        self.conf['community'] = conf.get('community', None)
        if not self.conf['community']:
            raise errors.ConfigError(conf, "SNMP community is required")

    def check_oid(self, conf, key):
        """Check/parse an oid"""
        try:
            oid = netsnmp.OID(conf[key])
        except netsnmp.OIDValueError, ex:
            raise errors.ConfigError(conf, str(ex))

        return oid


class Query_snmp(_Query_snmp_common):
    """Fetch a single value via SNMP"""

    def __init__(self, conf):
        _Query_snmp_common.__init__(self, conf)

        if 'oid' in conf:
            if ("oid_base" in conf or "oid_key" in conf or "key" in conf):
                raise errors.ConfigError(conf,
                        "oid cannot be used with oid_base, oid_key, and key")

            self.conf['oid'] = self.check_oid(conf, 'oid')

            conf['walk'] = False
            self.query_oid = addQuery(conf, qcls=_Query_snmp_combined)
            self.addDependency(self.query_oid)

        elif ("oid_base" in conf and "oid_key" in conf and "key" in conf):
            if "oid" in conf:
                raise errors.ConfigError(conf,
                        "oid cannot be used with oid_base, oid_key, and key")

            self.conf['oid_base'] = self.check_oid(conf, 'oid_base')
            self.conf['oid_key'] = self.check_oid(conf, 'oid_key')
            self.conf['key'] = conf['key']

            base = conf.copy()
            base['walk'] = True
            base['oid'] = self.conf['oid_base']
            self.query_base = addQuery(base, qcls=_Query_snmp_combined)
            self.addDependency(self.query_base)

            key = conf.copy()
            key['walk'] = True
            key['oid'] = self.conf['oid_key']
            self.query_key = addQuery(key, qcls=_Query_snmp_combined)
            self.addDependency(self.query_key)
        else:
            raise errors.ConfigError(conf,
                    "oid or oid_base, oid_key, and key are required")

    def _start(self):
        """Get and filter the result the from combined query."""

        try:
            if "oid" in self.conf:
                return self._get_result()
            else:
                return self._get_result_set()
        except:
            return errors.Failure()

    def _get_result(self):
        """Get a single oid value"""

        result = self.query_oid.result
        if isinstance(result, failure.Failure):
            return result

        oid = self.conf['oid']
        result = dict(self.query_oid.result)
        if oid not in result:
            raise errors.TestCritical("No value received for %s" % (oid,))

        return str(result[oid])

    def _get_result_set(self):
        """Get the requested value from the oid_base set.

        Matches the value index from the oid_key set specified
        by the key field to retreive the oid_base value.
        """

        class Return(Exception):
            pass

        def filter_result(result, root):
            if isinstance(result, failure.Failure):
                raise Return(result)

            new = {}
            for key, value in result:
                if key.startswith(self.conf[root]):
                    new[key] = value

            if not new:
                raise errors.TestCritical("No values received for %s" % (root,))

            return new

        try:
            base = filter_result(self.query_base.result, "oid_base")
            keys = filter_result(self.query_key.result, "oid_key")
        except Return, ex:
            return ex.args[0]

        final = None
        for oid, value in keys.iteritems():
            if value == self.conf["key"]:
                index = oid[len(self.conf["oid_key"]):]
                final = self.conf['oid_base'] + index
                break

        if final is None:
            raise errors.TestCritical("key not found: %r" % self.conf["key"])

        if final not in base:
            raise errors.TestCritical("No value received for %s" % (final,))

        return str(base[final])


class _Query_snmp_combined(_Query_snmp_common):
    """Combined Query used to send just one query to common host."""

    def __init__(self, conf):
        """Initialize query with oids and host port information."""
        _Query_snmp_common.__init__(self, conf)

        self.oids = set()
        self.update(conf)
        self.conf['walk'] = conf['walk']

        # Don't combine version 1 queries because the response can only
        # report one error and we can't tell if the others are ok or not
        if self.conf['version'] == "1":
            self.conf['oids'] = self.oids

        try:
            self.client = SnmpSession(
                    version=self.conf['version'],
                    community=self.conf['community'],
                    # Retry after 1 second for 'timeout' retries
                    timeout=1, retrys=int(self.conf['timeout']),
                    peername=self.conf['addr'])
        except netsnmp.SnmpError, ex:
            raise errors.InitError("Snmp Error: %s" % ex)

    def update(self, conf):
        """Update compound query with oids to be retreived from host."""
        self.oids.add(self.check_oid(conf, 'oid'))

    def _start(self):
        try:
            self.client.open()
            if self.conf['walk']:
                deferred = self.client.walk(self.oids, strict=True)
            else:
                deferred = self.client.get(self.oids)
        except:
            return errors.Failure()

        deferred.addBoth(self._handle_close)
        deferred.addErrback(self._handle_error)
        return deferred

    @errors.callback
    def _handle_close(self, result):
        """Close the SNMP connection socket"""
        self.client.close()
        return result

    @errors.callback
    def _handle_error(self, result):
        if isinstance(result.value, neterror.TimeoutError):
            raise errors.TestCritical("SNMP request timeout")
        return result

# Unix and NTP have different epoch values
TIME1970 = 2208988800L

class NTPProtocol(protocol.DatagramProtocol):

    noisy = False

    def __init__(self, host, port, deferred):
        """cb is a function to call with a time"""
        self.host = host
        self.port = port
        self.deferred = deferred

    def startProtocol(self):
        self.transport.connect(self.host, self.port)
        self.transport.write('\x1b' + 47 * '\0')

    def datagramReceived(self, data, addr):
        if len(data) != 12*4:
            self.deferred.errback(errors.Failure(errors.TestCritical(
                "Invalid packet size: %s" % len(data))))

        pkt = struct.unpack('!12I', data)
        self.deferred.callback(str(pkt[10] - TIME1970))

    def connectionRefused(self):
        self.deferred.errback(errors.Failure(
            errors.TestCritical("Connection Refused")))


class Query_ntp(Query):
    """Fetch the time from a NTP server"""

    def __init__(self, conf):
        Query.__init__(self, conf)
        self.conf['addr'] = self.addr
        self.conf['port'] = int(conf.get('port', 123))

    def _start(self):
        deferred = defer.Deferred()
        protocol = NTPProtocol(self.addr, self.conf['port'], deferred)
        listener = reactor.listenUDP(0, protocol)
        timeout = reactor.callLater(self.conf['timeout'],
                lambda: deferred.errback(errors.Failure(errors.TestCritical(
                        "Timeout waiting for NTP response"))))

        def stop(result):
            if timeout.active():
                timeout.cancel()
            listener.stopListening()
            return result

        deferred.addBoth(stop)
        return deferred


##############################
# Oracle-specific SQL queries
##############################

class _DBColumn:
    """describes the name and type of a column, to facilitate mapping the
    attributes of a DB column into XML attribs (taken by processing
    the contents of a cx_Oracle.Cursor.description)"""

    # taken from http://cx-oracle.sourceforge.net/html/cursor.html
    CX_VAR_COLUMNS = ('name', 'type', 'display_size', 'internal_size',
                     'precision', 'scale', 'null_ok')

    def __init__(self, desc):
        """Take the decription of a cx_Oracle variable, and make it an actual
        object"""

        # these are the attributes that this item will contain
        for k,v in zip(self.CX_VAR_COLUMNS, desc):
            setattr(self, k, v)
    def __str__(self):
        return "<_DBColumn %s:%s>" % (self.name, self.type)
    def __repr__(self):
        return str(self)


class _OracleConnectionPool(adbapi.ConnectionPool):
    """a specialized connectionPool, with a modified _runQuery that fires with
    the variables of the cursor as well as the the result"""

    #! this makes me twitch, but I can't think of a better way to get the list of
    #! variables out of the otherwise inaccessible cursor
    def _runQuery(self, cursor, *args, **kwargs):
        """Override the adbpapi.ConnectionPool._runQuery, to remember and return
        the cursor, as well as the resulting data"""

        # the parent-class _runQuery() returns the result of cursor.fetchall(),
        # which might be dangerous if a rogue query were to return a huge dataset.
        result = adbapi.ConnectionPool._runQuery(self, cursor, *args, **kwargs)
        columns = map(lambda c: _DBColumn(c), cursor.description)
        return (columns, result)


class Query_oraclesql(Query):
    """Use oracle sql to execute a query against one of the databases via
    twisted's adbapi"""

    # the field of the configuration struct that we care about
    CONF_FIELDS = ['user', 'password', 'dsn', 'sql', 'binds']

    def __init__(self, conf):
        if not etree or not cx_Oracle:
            raise errors.InitError(
                    "cx_Oracle and lxml are required for Oracle support.")

        Query.__init__(self, conf)
        # need to make this take a tnsname system instead of just a DBI
        for fieldname in self.CONF_FIELDS:
            if fieldname in conf:
                self.conf[fieldname] = conf.get(fieldname)

    def _start(self):
        self.dbpool = _OracleConnectionPool('cx_Oracle', user=self.conf['user'],
                                          password=self.conf['password'],
                                          dsn=self.conf['dsn'],
                                          threaded=True,
                                          cp_reconnect=True)
        log.debug("running sql %s", self.conf['sql'])
        self.deferred = self.dbpool.runQuery(self.conf['sql'],
                                             self.conf.get('binds', {}))
        self.deferred.addCallback(self._success)
        self.deferred.addErrback(self._failure_oracle)
        return self.deferred

    def _success(self, result):
        """success receives a (columns, data) pair, where 'columns' is a list of
        _DBColumns and 'data' is the actual data returned from the query.
        Convert it to XML and return it
        """
        columns, table = result
        tree = _result_as_xml(columns, table)
        self.result = etree.tostring(tree, pretty_print=False)
        log.debug("Query_oraclesql success: %s rows returned", len(table))
        self._cleanup()
        return self.result

    @errors.callback
    def _failure_oracle(self, result):
        """Catch common oracle failures here"""
        log.debug("Fail! %s", result.value)
        # cleanup now, since we mightn't be back
        self._cleanup()
        raise_oracle_warning(result)

    def _cleanup(self):
        """Closes the ConnectionPool"""
        self.dbpool.close()


class Query_oracle_plsql(Query):
    """A query that uses cx_oracle directly (allowing for stored procedure calls)
    results (via "out" parameters) are returned in XML
    """
    # fields we expect to see in the conf
    CONF_FIELDS = ['user', 'password', 'dsn', 'procedure', 'parameters', 'DBI']

    # these are the orderings for the parameters in the config. I would have
    # preferred to specify the parameters as dicts, but coil apparently does not
    # support that yet.
    IN_PARAMETER_FIELDS = ['direction', 'name', 'value']
    OUT_PARAMETER_FIELDS = ['direction', 'name', 'type']

    def __init__(self, conf):
        if not etree or not cx_Oracle:
            raise errors.InitError(
                "cx_Oracle and lxml are required for Oracle support.")
        Query.__init__(self, conf)
        for fieldname in self.CONF_FIELDS:
            if fieldname in conf:
                self.conf[fieldname] = conf.get(fieldname)

        self.check_config(conf)

        # setup the DBI, if we don't have it
        if "DBI" not in self.conf:
            self.conf['DBI'] = "%s/%s@%s" % (
                self.conf['user'], self.conf['password'], self.conf['dsn'])

        # data members to be filled in later
        self.connection = None
        self.parameters = None
        self.cursor = None


    def check_config(self, conf):
        """check the config for semantic errors"""

        if not ('user' in self.conf and 'password' in self.conf
                and 'dsn' in self.conf) and not 'DBI' in self.conf:
            raise errors.ConfigError(conf,
                "needs values for user, password, dsn or for DBI")

        if 'procedure' not in self.conf:
            raise errors.ConfigError(conf, "needs a 'procedure' name to call")

        # check the format of the parameters list.
        for param in self.conf['parameters']:
            if not isinstance(param, list):
                raise errors.ConfigError(conf, '%s should be a list of lists'
                                        % self.conf['parameters'])

            if len(param) != 3 or not param[0] in ['out', 'in']:
                msg = ("%s should be a list of three elements: "
                       "[ <in|out> <param_name> <type|value>" % param)
                raise errors.ConfigError(conf, msg)


    def buildparam(self, p):
        """Parameters in the conf are in list form. Convert them to dicts (including
        suitable DB variables where relevant) for easier sending/receiving"""

        def makeDBtype(s):
            "convert to the name of a cx_Oracle type, using the much-dreaded eval()"
            try:
                return eval('cx_Oracle.' + s.upper())
            except AttributeError as err:
                raise TypeError("'%s' is not a recognized Oracle type" % s)

        if p[0].lower() == 'in':
            retval = dict(zip(self.IN_PARAMETER_FIELDS, p))
            retval['db_val'] = retval['value']
            return retval
        elif p[0].lower() == 'out':
            retval = dict(zip(self.OUT_PARAMETER_FIELDS, p))
            retval['db_val'] = self.cursor.var(makeDBtype(retval['type']))
            return retval
        else:
            raise errors.InitError(
                "Unrecognized direction '%s' in %s (expected 'in' or 'out')" % (p[0], p))


    def _start(self):
        log.debug("running procedure")

        ## Should do some connection pooling here...
        self.connection = cx_Oracle.Connection(self.conf['DBI'], threaded=True)
        self.cursor = self.connection.cursor()

        self.parameters = [self.buildparam(p) for p in self.conf['parameters']]
        # result is a modified copy of self.parameters

        #result = self.callproc(self.conf['query.procedure'], self.parameters)
        db_params = [p['db_val']  for p in self.parameters]
        self.deferred = threads.deferToThread(self.cursor.callproc,
                                              self.conf['procedure'],
                                              db_params)
        self.deferred.addCallback(self._success)
        self.deferred.addErrback(self._failure_oracle)
        return self.deferred

    @errors.callback
    def _failure_oracle(self, result):
        log.debug("Fail! %s", result.value)
        self._cleanup()
        raise_oracle_warning(result)

    def _cleanup(self):
        """Closes the DB connection"""
        self.connection.close()

    def _success(self, result):
        """Callback for the deferred that handles the procedure call"""
        self.result = self._outparams_as_xml(result)
        self._cleanup()
        return self.result

    def _outparams_as_xml(self, result_set):
        """Convert the 'out' parameters into XML. """

        def only_out_params(resultset):
            """(too big for a lambda) only convert those parameters that were
            direction='out', along with their matching definitions from the conf"""
            return [p for p in zip(self.parameters, result_set)
                    if p[0]['direction'] == 'out']
        try:
            root = etree.Element('result')
            for param, db_value in only_out_params(result_set):
                if not isinstance(db_value, cx_Oracle.Cursor):
                    # for non-cursor results, all is treated as text
                    tree = etree.Element(param['name'], type="STRING")
                    if db_value: tree.text = str(db_value)
                else:
                    # for cursors, we will convert to tables
                    columns = map(_DBColumn, db_value.description)
                    table = db_value.fetchall()
                    tree = _result_as_xml(columns, table, param['name'])
                root.append(tree)
            return etree.tostring(root, pretty_print=False)

        except Exception as err:
            raise errors.TestCritical("XML conversion error!: %s" % err)


def _result_as_xml(columns, result_table, name="queryresult"):
        """Convert an executed query into XML, using the columns to get the
        names and types of the column tags"""

        # example query: select 1 as foo from dual
        # returns: '<queryresult><row><foo type="NUMBER">1</foo></row></queryresult>'
        try:
            tree = etree.Element(name)
            for row in result_table:
                xmlrow = etree.Element('row')
                for col, val in zip(columns, row):
                    xmlrow.append(_xml_element(col, val))
                tree.append(xmlrow)
            return tree
        except Exception as err:
            raise errors.TestCritical("XML conversion error!: %s" % err)


def _xml_element(col, value):
        name = re.sub("[^\w]","", col.name.lower())
        elt = etree.Element(name, type=col.type.__name__)
        if value != None:
            elt.text = str(value)
        return elt


def raise_oracle_warning(failure):
    """A handy wrapper for handling cx_Oracle failures in Query_* objects"""

    if isinstance(failure.value, cx_Oracle.Warning):
        # Exception raised for important warnings and defined by the DB API
        # but not actually used by cx_Oracle.
        raise errors.TestWarning(failure.value)

    if isinstance(failure.value, cx_Oracle.InterfaceError):
        # Exception raised for errors that are related to the database
        # interface rather than the database itself. It is a subclass of
        # Error.
        raise errors.TestCritical(failure.value)

    if isinstance(failure.value, cx_Oracle.DatabaseError):
        # Exception raised for errors that are related to the database. It
        # is a subclass of Error.
        raise errors.TestCritical(failure.value)

    if isinstance(failure.value, cx_Oracle.Error):
        # Exception that is the base class of all other exceptions
        # defined by cx_Oracle and is a subclass of the Python
        # StandardError exception (defined in the module exceptions).
        raise errors.TestCritical(failure.value)

    log.debug("Unhandled failure! %s", failure)

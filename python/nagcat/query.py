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

try:
    import uuid
except ImportError:
    uuid = None

from twisted.internet import reactor, defer, protocol, process
from twisted.internet import error as neterror
from twisted.web import error as weberror
from twisted.web.client import HTTPClientFactory
from twisted.python.util import InsensitiveDict
from twisted.python import failure

# SSL support is screwy
try:
   from twisted.internet import ssl
except ImportError:
   # happens the first time the interpreter tries to import it
   ssl = None
if ssl and not ssl.supported:
   # happens second and later times
   ssl = None

# SNMP support
try:
    from pynetsnmp import netsnmp, twistedsnmp
except ImportError:
    netsnmp = None

from nagcat import errors, log, scheduler

_queries = {}

def addQuery(conf, qcls=None):
    """Create a new query and register it or return an existing one"""

    qtype = conf.get('type')

    # Find the correct Query class for this type
    if not qcls:
        qcls = globals().get('Query_%s' % qtype, None)

    if qcls is not None:
        qobj = qcls(conf)
    else:
        raise errors.ConfigError(conf, "Unknown query type '%s'" % qtype)

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
        self.conf['headers'] = conf.get('headers', {})

        # Some versions of twisted will send Host twice if it is in the
        # headers dict. Instead we set factory.host.
        if self.conf['port'] == self.port:
            self.headers_host = self.host
        else:
            self.headers_host = "%s:%s" % (self.host, self.conf['port'])

        # We need to make sure headers is a dict.
        self.headers = InsensitiveDict()
        for (key, val) in self.conf['headers'].iteritems():
            if key.lower() == 'host':
                self.headers_host = val
            else:
                self.headers[key] = val

        # Also use a convert to a lower-case only dict for self.conf so
        # that queries that differ only by case are still shared.
        self.conf['headers'] = InsensitiveDict(preserve=0)
        self.conf['headers']['host'] = self.headers_host
        self.conf['headers'].update(self.headers)

        if self.conf['data']:
            self.method = "POST"
        else:
            self.method = "GET"

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

class Query_snmp_common(Query):
    """Parent class for both Query_snmp and QuerySnmp_combined."""
    OID = re.compile("^\.?\d+(\.\d+)*$")

    def check_oid(self, oid):
        """
        Check that oid matches the expected regex pattern.
        Make sure first char is '.'.
        """
        if not self.OID.match(oid):
            raise errors.ConfigError(conf,
                                     "Invalid SNMP OID '%s'" % oid)
        if oid[0] != '.':
            return ".%s" % oid
        return oid

    def oid_set(self, oid):
        """Get the oid set value lookup for an oid value."""
        oid_set =  ".".join(oid.split(".")[:-1])
        return self.check_oid(oid_set)

class Query_snmp(Query_snmp_common):
    """Fetch a single value via SNMP"""

    def __init__(self, conf):
        if netsnmp is None:
            raise errors.InitError("pynetsnmp is required for SNNP support.")
        Query.__init__(self, conf)

        self.conf['addr'] = self.addr
        self.conf['port'] = int(conf.get('port', 161))

        if 'oid' in conf:
            self.conf['oid'] = self.check_oid(conf['oid'])
            self.conf['oid_set'] = self.oid_set(conf['oid'])
            if ("oid_base" in self.conf or
                "oid_key" in self.conf or "key" in self.conf):
                raise errors.ConfigError(conf,
                      "oid_base, oid_key and key not needed if oid is set.")
        elif ("oid_base" in conf and
              "oid_key" in conf and "key" in conf):
            self.conf['oid_base'] = self.check_oid(conf['oid_base'])
            self.conf['oid_key'] = self.check_oid(conf['oid_key'])
            self.conf['key'] = conf['key']
        else:
            raise errors.ConfigError(conf,
                  "oid_base, oid_key and key need to be set if oid not set.")

        self.conf['version'] = str(conf.get('version', '2c'))
        self.conf['community'] = conf.get('community')

        if self.conf['version'] not in ('1', '2c'):
            raise errors.ConfigError(conf,
                    "Invalid SNMP version '%s'" % conf['version'])

        # add single Query class per host address that
        # does the actual retreival of data
        self.query_combined = addQuery(conf, qcls=Query_snmp_combined)
        self.addDependency(self.query_combined)

    def _start(self):
        """Get data structure from combined query.

        Get the result data table from combined query.
        Retreive the relevant value for the query and return it.
        """
        result = self.query_combined.result

        if isinstance(result, failure.Failure):
            return result
        elif "oid" in self.conf:
            return self.get_oid_from_result(result)
        else:
            return self.get_oid_set_from_result(result)

    def check_lookup(self, oid_key, lookup_table):
        """Check that key is in dictionary. Throw exception if it is not."""
        if oid_key not in lookup_table or lookup_table[oid_key] is None:
            raise errors.TestCritical("No oid set returned %s for" %
                                      oid_key)

    def get_oid_from_result(self, result):
        """Retreive the oid value information from the result set."""
        self.check_lookup(self.conf["oid_set"], result)
        self.check_lookup(self.conf["oid"], result[self.conf["oid_set"]])

        return str(result[self.conf["oid_set"]][self.conf["oid"]])

    def get_oid_set_from_result(self, result):
        """Retreive the oid value from the oid_base set.

        Matches the value index from the oid_key set specified
        by the key field to retreive the oid_base value.
        """
        self.check_lookup(self.conf["oid_base"], result)
        oid_base_dict = result[self.conf["oid_base"]]

        self.check_lookup(self.conf["oid_key"], result)
        oid_keys_dict = result[self.conf["oid_key"]]

        for key in oid_keys_dict.keys():
            if self.conf["key"] == oid_keys_dict[key]:
                relevant_index = key.split(".")[-1].strip()
                oid_lookup = self.conf['oid_base'] + "." + relevant_index
                break
        else:
            raise errors.TestCritical("No oid_key match for: '%s'." %
                                      self.conf["key"])

        self.check_lookup(oid_lookup, oid_base_dict)
        return str(oid_base_dict[oid_lookup])


class Query_snmp_combined(Query_snmp_common):
    """Combined Query used to send just one query to common host."""

    def __init__(self, conf):
        """Initialize query with oids and host port information."""
        if netsnmp is None:
            raise errors.InitError("pynetsnmp is required for SNNP support.")

        Query.__init__(self, conf)

        self.conf['addr'] = self.addr
        self.conf['port'] = int(conf.get('port', 161))
        self.oids = set()

        self.conf['version'] = str(conf.get('version', '2c'))
        self.conf['community'] = conf.get('community')

        if self.conf['version'] not in ('1', '2c'):
            raise errors.ConfigError(conf,
                    "Invalid SNMP version '%s'" % conf['version'])
        self.update(conf)

        self._client = twistedsnmp.AgentProxy(
                self.addr, self.conf['port'],
                self.conf['community'], self.conf['version'])

        try:
            self._client.open()
        except netsnmp.SnmpError, ex:
            raise errors.InitError(str(ex))

    def __str__(self):
        """Compound query only displays host and port in repr."""
        return "<%s  %s:%s>" % (self.__class__.__name__,
                                self.conf['addr'], self.conf['port'])

    def _start(self):
        # Use half of the timeout and allow 1 retry,
        # this probably isn't great but should be ok.
        deferred = self._client.getTable(
            (tuple(self.oids)),
            timeout=self.conf['timeout']/2, retryCount=1)

        deferred.addCallback(self._handle_result)
        deferred.addErrback(self._handle_error)
        return deferred

    def _handle_result(self, result):
        """Callback handler sets result to data member of query."""
        self.result = result
        return result

    @errors.callback
    def _handle_error(self, result):
        if isinstance(result.value, neterror.TimeoutError):
            raise errors.TestCritical("SNMP request timeout")
        return result

    def update(self, conf):
        """Update compound query with oids to be retreived from host."""
        if 'oid' in conf:
            oid = ".".join(conf['oid'].split(".")[:-1])
            self.oids.add(self.check_oid(oid))
        if 'oid_base' in conf:
            self.oids.add(self.check_oid(conf['oid_base']))
        if 'oid_key' in conf:
            self.oids.add(self.check_oid(conf['oid_key']))

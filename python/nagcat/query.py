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
import signal

from twisted.internet import reactor, defer, protocol, process
from twisted.internet import error as neterror
from twisted.web import error as weberror
from twisted.web.client import HTTPClientFactory
from twisted.python.util import InsensitiveDict
from twisted.python import failure
from coil import struct

# SSL support is screwy
try:
   from twisted.internet import ssl
except ImportError:
   # happens the first time the interpreter tries to import it
   ssl = None
if ssl and not ssl.supported:
   # happens second and later times
   ssl = None

from nagcat import scheduler, util, log

_queries = {}

def addQuery(conf):
    """Create a new query and register it or return an existing one"""

    qtype = conf.get('type')

    # Find the correct Query class for this type
    qclass = globals().get('Query_%s' % qtype, None)
    if qclass is not None:
        qobj = qclass(conf)
    else:
        raise Exception("Unknown query type '%s'" % qtype)

    key = repr(qobj)
    if key in _queries:
        log.debug("Reusing query '%s'", key)
        qobj = _queries[key]
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
        assert isinstance(conf, struct.Struct)
        conf.expand(recursive=False)
        host = conf.get('host', None)
        scheduler.Runnable.__init__(self, conf.get('repeat', None), host)

        # self.conf must contain all configuration variables that
        # this object uses so identical Queries can be identified.
        self.conf = {}

        # All queries should handle timeouts
        try:
            self.conf['timeout'] = float(conf.get('timeout', 15))
        except ValueError:
            raise util.KnownError("Invalid timeout value '%s'" %
                    conf.get('timeout'))

        if self.conf['timeout'] <= 0:
            raise util.KnownError("Non-positive timeout value '%s'" %
                    conf.get('timeout'))

    def _failure_tcp(self, result):
        """Catch common TCP failures and convert them to a KnownError"""

        if isinstance(result.value, neterror.TimeoutError):
            result = failure.Failure(util.KnownError(
                "TCP handshake timeout", state="CRITICAL", error=result.value))

        elif isinstance(result.value, neterror.ConnectionRefusedError):
            result = failure.Failure(util.KnownError(
                "TCP connection refused", state="CRITICAL", error=result.value))

        elif isinstance(result.value, neterror.ConnectError):
            # ConnectError sometimes is used to wrap up various other errors.
            result = failure.Failure(util.KnownError(
                "TCP connection error", state="CRITICAL", error=result.value))

        return result

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.conf)


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
        self.conf['host'] = conf.get('host')
        self.conf['port'] = int(conf.get('port', self.port))
        self.conf['path'] = conf.get('path', '/')
        self.conf['data'] = conf.get('data', None)
        self.conf['headers'] = conf.get('headers', {})

        # Some versions of twisted will send Host twice if it is in the
        # headers dict. Instead we set factory.host.
        if self.conf['port'] == self.port:
            self.headers_host = self.conf['host']
        else:
            self.headers_host = "%s:%s" % (self.conf['host'], self.conf['port'])

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

    def _failure_http(self, result):
        """Convert HTTP specific failures to a KnownError"""

        if isinstance(result.value, defer.TimeoutError):
            result = failure.Failure(util.KnownError(
                "Timeout waiting on HTTP response",
                state="CRITICAL", error=result.value))

        elif isinstance(result.value, weberror.PageRedirect):
            # Redirects aren't actually an error :-)
            result = "%s\n%s" % (result.value, result.value.location)

        elif isinstance(result.value, weberror.Error):
            result = failure.Failure(util.KnownError(
                "HTTP Error %s" % result.value,
                state="CRITICAL", error=result.value))

        return result

    def _connect(self, factory):
        # Split out the reactor.connect call to allow for easy
        # overriding in HTTPSQuery
        reactor.connectTCP(self.conf['host'], self.conf['port'],
                factory, self.conf['timeout'])


class Query_https(Query_http):
    """Process an HTTP GET or POST over SSL"""

    scheme = "https"
    port = 443

    def __init__(self, conf):
        if ssl is None:
            raise util.KnownError("Attempted to create an HTTPS test but "
                    "the system does not support SSL. Try installing the "
                    "OpenSSL python module.")
        Query_http.__init__(self, conf)

    def _connect(self, factory):
        context = ssl.ClientContextFactory()
        reactor.connectSSL(self.conf['host'], self.conf['port'],
                factory, context, self.conf['timeout'])

class RawProtocol(protocol.Protocol):
    """Basic protocol handler for raw TCP/SSL queries.

    This and its factory are modeled after the twisted.web HTTP client.
    """

    expected_loss = False

    def connectionMade(self):
        self.result = ""
        if self.factory.conf['data']:
            self.transport.write(self.factory.conf['data'])
        # TODO: add other shutdown methods?
        self.transport.loseWriteConnection()

    def dataReceived(self, data):
        self.result += data
        self.expected_loss = True

    def timeout(self):
        self.factory.failed(failure.Failure(util.KnownError(
            "Timeout waiting for data", self.result, "CRITICAL")))
        self.expected_loss = True
        self.transport.loseConnection()

    def connectionLost(self, reason):
        if self.expected_loss:
            self.factory.result(self.result)
        else:
            self.factory.failed(reason)


class RawFactory(protocol.ClientFactory):
    """Handle raw TCP/SSL queries"""

    noisy = False
    protocol = RawProtocol

    def __init__(self, conf):
        self.conf = conf
        self.waiting = True
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
        self.failed(reason)

    def failed(self, reason):
        if self.waiting:
            self.waiting = False
            self.deferred.errback(reason)

    def result(self, result):
        if self.waiting:
            self.waiting = False
            self.deferred.callback(result)

class Query_tcp(Query):
    """Send and receive data over a raw TCP socket"""

    def __init__(self, conf):
        Query.__init__(self, conf)

        self.conf['host'] = conf.get('host')
        self.conf['port'] = int(conf.get('port'))
        self.conf['data'] = conf.get('data', None)

    def _start(self):
        factory = RawFactory(self.conf)
        factory.deferred.addErrback(self._failure_tcp)
        self._connect(factory)
        return factory.deferred

    def _connect(self, factory):
        reactor.connectTCP(self.conf['host'], self.conf['port'],
                factory, self.conf['timeout'])

class Query_ssl(Query_tcp):
    """Send and receive data over a raw SSL socket"""

    def __init__(self, conf):
        if ssl is None:
            raise util.KnownError("Attempted to create a SSL test but "
                    "the system does not support SSL. Try installing the "
                    "OpenSSL python module.")
        Query_tcp.__init__(self, conf)

    def _connect(self, factory):
        context = ssl.ClientContextFactory()
        reactor.connectSSL(self.conf['host'], self.conf['port'],
                factory, context, self.conf['timeout'])

class SubprocessProtocol(protocol.ProcessProtocol):
    """Handle input/output for subprocess queries"""

    timeout = False

    def connectionMade(self):
        self.result = ""
        if self.factory.conf['data']:
            self.transport.write(self.factory.conf['data'])
        self.transport.closeStdin()

    def outReceived(self, data):
        self.result += data

    def timeout(self):
        self.timeout = True
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
            if self.timeout:
                result = failure.Failure(util.KnownError(
                    "timeout waiting for command to finish",
                    self.result, "CRITICAL", reason.value))
            elif reason.value.exitCode == 127:
                result = failure.Failure(util.KnownError(
                    "command not found",
                    self.result, "CRITICAL", reason.value))
            else:
                result = failure.Failure(util.KnownError(
                    reason.value.args[0],
                    self.result, "CRITICAL", reason.value))

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
                environment={}, path=None, proto=proto)

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

        self.conf['command'] = conf.get('command')
        self.conf['data'] = conf.get('data', "")

    def _start(self):
        proc = SubprocessFactory(self.conf)
        return proc.deferred

class NetSnmpFactory(SubprocessFactory):
    """Run an SNMP query using snmpget"""

    def __init__(self, conf):
        self.conf = conf
        self.deferred = defer.Deferred()

        # Retry once per second until timeout is up
        retry = int(conf['timeout']) - 1
        if retry < 0:
            retry = 0

        agent = "%s:%s:%s" % (conf['protocol'], conf['host'], conf['port'])
        cmd = ('snmpget', '-v', conf['version'], '-c', conf['community'],
                '-t', '1', '-r', retry, agent, conf['oid'])

        # Allow the process a second to die
        self.conf['timeout'] += 1
        # Pass nothing to stdin
        self.conf['data'] = ""

        self._startProcess(cmd)

    def result(self, data):
        # Strip off the "[oid name] = " prefix
        if isinstance(data, str):
            data = re.sub("^\S+ = ", "", data)
        SubprocessFactory.result(self, data)

class Query_snmp(Query):
    def __init__(self, conf):
        Query.__init__(self, conf)

        self.conf['protocol'] = conf.get('protocol', 'udp')
        self.conf['host'] = conf.get('host')
        self.conf['port'] = int(conf.get('port', 161))
        self.conf['oid'] = conf.get('oid')
        self.conf['version'] = str(conf.get('version', '2c'))
        self.conf['community'] = conf.get('community')

        if self.conf['version'] not in ('1', '2c'):
            raise util.KnownError("Invalid SNMP version '%s'" %
                    self.conf['version'])

    def _start(self):
        proc = NetSnmpFactory(self.conf)
        return proc.deferred

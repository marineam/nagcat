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

"""TCP Queries"""

from zope.interface import classProvides
from twisted.internet import reactor, defer, protocol

# SSL support is screwy
try:
   from twisted.internet import ssl
except ImportError:
   # happens the first time the interpreter tries to import it
   ssl = None
if ssl and not ssl.supported:
   # happens second and later times
   ssl = None

from nagcat import errors, query

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

class TCPQuery(query.Query):
    """Send and receive data over a raw TCP socket"""

    classProvides(query.IQuery)

    name = "tcp"

    def __init__(self, nagcat, conf):
        super(TCPQuery, self).__init__(nagcat, conf)

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

class SSLQuery(TCPQuery):
    """Send and receive data over a raw SSL socket"""

    classProvides(query.IQuery)

    name = "ssl"

    def __init__(self, nagcat, conf):
        if ssl is None:
            raise errors.InitError("pyOpenSSL is required for SSL support.")
        super(SSLQuery, self).__init__(nagcat, conf)

    def _connect(self, factory):
        context = ssl.ClientContextFactory()
        reactor.connectSSL(self.addr, self.conf['port'],
                factory, context, self.conf['timeout'])

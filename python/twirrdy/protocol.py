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

"""rrdcached protocol"""

from collections import deque

from twisted.internet import defer, error, interfaces
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols import basic
from twisted.python import failure, log
from zope.interface import implements

class RRDCacheError(Exception):
    """rrdcached responded with an error"""

class RRDCacheProtocol(basic.LineOnlyReceiver, object):

    delimiter = '\n'
    _deferred = None

    def connectionMade(self):
        self.waiting = deque()
        self.response_length = 0
        self.response_buffer = []

        if self._deferred:
            deferred = self._deferred
            self._deferred = None
            deferred.callback(None)

    def sendLine(self, line):
        """Send command, return a deferred.

        The final result will be the text of the response or a Failure
        if the connection was lost before the response came.

        BATCH commands are currently not supported.
        """
        line = line.strip()
        assert self.delimiter not in line
        assert not line.upper().startswith('BATCH')
        super(RRDCacheProtocol, self).sendLine(line)
        deferred = defer.Deferred()
        self.waiting.append(deferred)
        return deferred

    def lineReceived(self, line):
        """Process responses, reported command status"""
        line = line.strip()
        if not line:
            return
        if not self.response_length:
            length = line.split(None, 1)[0]
            try:
                self.response_length = int(length) + 1
            except ValueError:
                return error.ConnectionLost("Unexpected data: %r" % line)

        self.response_buffer.append(line)
        current_length = len(self.response_buffer)

        # We have filled the buffer, fire off the complete response
        if current_length == self.response_length:
            deferred = self.waiting.popleft()
            deferred.callback(self.delimiter.join(self.response_buffer))
            self.response_buffer = []

        # The response indicated an error, there is no buffered lines
        elif self.response_length <= 0:
            assert current_length == 1
            deferred = self.waiting.popleft()
            deferred.errback(RRDCacheError(line))
            self.response_buffer = []

        # More lines are expected
        else:
            assert current_length < self.response_length

    def connectionLost(self, reason):
        """Report lost connection to waiting commands"""
        while self.waiting:
            deferred = self.waiting.popleft()
            deferred.errback(reason)

class RRDCacheClient(ReconnectingClientFactory, object):
    """A reconnecting client factory that can pause producing"""

    # We provide a "streaming" producer
    implements(interfaces.IPushProducer)

    protocol = RRDCacheProtocol
    maxDelay = 30 # seconds

    def __init__(self, deferred=None, noisy=False):
        self._deferred = deferred
        self._protocol = None
        self._paused = True
        self.noisy = noisy

    def buildProtocol(self, addr):
        if self.noisy:
            log.msg("%s building protocol" % self)
        p = super(RRDCacheClient, self).buildProtocol(addr)
        p._deferred = self._deferred
        self._protocol = p
        self._deferred = None
        self.resumeProducing()
        self.resetDelay()
        return p

    def clientConnectionFailed(self, connector, reason):
        super(RRDCacheClient, self).clientConnectionFailed(connector, reason)

        if self._deferred:
            deferred = self._deferred
            self._deferred = None
            deferred.errback(None)

    def startedConnecting(self, connector):
        connector.transport.registerProducer(self, streaming=True)

    def stopProducing(self):
        if self.noisy:
            log.msg("%s stopped" % self)
        self._paused = True
        self._protocol = None

    def pauseProducing(self):
        if self.noisy:
            log.msg("%s paused" % self)
        self._paused = True

    def resumeProducing(self):
        if self.noisy:
            log.msg("%s resumed" % self)
        assert self._protocol
        self._paused = False

    def sendLine(self, line):
        """Submit a line if possible"""

        if self.noisy:
            log.msg("%s sending %r" % (self, line))

        if not self._paused:
            try:
                return self._protocol.sendLine(line)
            except Exception:
                return defer.fail(failure.Failure())
        else:
            return defer.fail(error.ConnectionClosed("Not connected"))

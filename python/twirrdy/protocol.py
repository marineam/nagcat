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

from twirrdy import RRDToolError

class RRDCacheError(RRDToolError):
    """rrdcached responded with an error"""

class RRDCacheProtocol(basic.LineOnlyReceiver, object):

    delimiter = '\n'

    def connectionMade(self):
        self.waiting = deque()
        self.response_length = 0
        self.response_buffer = []
        self.factory.clientConnectionMade(self)

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
            self.response_length = 0

        # The response indicated an error, there is no buffered lines
        elif self.response_length <= 0:
            assert current_length == 1
            deferred = self.waiting.popleft()
            deferred.errback(RRDCacheError(line))
            self.response_buffer = []
            self.response_length = 0

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
    maxQueue = 1000

    def __init__(self, deferred=None, noisy=False):
        self._deferred = deferred
        self._protocol = None
        self._paused = True
        self._queue = deque(maxlen=self.maxQueue)
        self.noisy = noisy

    def clientConnectionMade(self, protocol):
        if self._deferred:
            deferred = self._deferred
            self._deferred = None
            deferred.callback(None)

        self._protocol = protocol
        self.resetDelay()
        self.resumeProducing()
        protocol.transport.registerProducer(self, streaming=True)

    def clientConnectionFailed(self, connector, reason):
        super(RRDCacheClient, self).clientConnectionFailed(connector, reason)

        if self._deferred:
            deferred = self._deferred
            self._deferred = None
            deferred.errback(reason)

    def stopProducing(self):
        log.msg("rrdcached connection stopped, buffering updates")
        self._paused = True
        self._protocol = None

    def pauseProducing(self):
        log.msg("rrdcached connection paused, buffering updates")
        self._paused = True

    def resumeProducing(self):
        assert self._protocol
        log.msg("rrdcached connection activated")
        self._paused = False
        self.flushLines()

    def flushLines(self):
        """Write out buffered lines"""

        if self._queue:
            log.msg("flushing updates to rrdcached")

        while self._queue and not self._paused:
            line, deferred = self._queue.popleft()
            try:
                response_deferred = self._protocol.sendLine(line)
                response_deferred.chainDeferred(deferred)
            except Exception:
                deferred.errback(failure.Failure())

    def sendLine(self, line):
        """Submit a line if possible"""

        if not self._paused:
            if self.noisy:
                log.msg("%s sending %r" % (self, line))

            try:
                return self._protocol.sendLine(line)
            except Exception:
                return defer.fail(failure.Failure())
        else:
            if self.noisy:
                log.msg("%s buffering %r" % (self, line))

            deferred = defer.Deferred()
            self._queue.append((line, deferred))
            return deferred

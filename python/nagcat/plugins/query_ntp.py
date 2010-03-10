# Copyright 2009-2010 ITA Software, Inc.
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

"""NTP Querys"""

import struct

from zope.interface import classProvides
from twisted.internet import reactor, defer, protocol

from nagcat import errors, query


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

class NTPQuery(query.Query):
    """Fetch the time from a NTP server"""

    classProvides(query.IQuery)

    name = "ntp"

    def __init__(self, conf):
        super(NTPQuery, self).__init__(conf)
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

    def __str__(self):
        # disable query grouping for ntp, it is light weight enough
        # and this allows snmp+ntp to be used without scheduling all
        # snmp tests at once as would happen if ntp queries are shared.
        return repr(self)

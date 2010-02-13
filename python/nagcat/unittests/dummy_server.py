# Copyright 2009 ITA Software, Inc.
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

"""Various dummy servers for use in unit tests."""


from email.parser import FeedParser
from zope.interface import implements
from twisted.internet import defer, interfaces, protocol, error
from twisted.python import failure
from twisted.web import resource, server
from twisted.mail import smtp

class Root(resource.Resource):
    """Root directory of the dummy web server"""

    def render_GET(self, request):
        return "hello\n";

    def render_POST(self, request):
        request.content.seek(0, 0)
        return request.content.read()

class HTTP(server.Site):
    """Dummy web server"""

    def __init__(self):
        root = resource.Resource()
        root.putChild("", Root())
        server.Site.__init__(self, root)

class Echo(protocol.Protocol):
    """TCP echo server, if no data given send 'hello'"""

    implements(interfaces.IHalfCloseableProtocol)

    def __init__(self):
        self.sent_data = False

    def dataReceived(self, data):
        self.transport.write(data)
        self.transport.loseConnection()
        self.sent_data = True

    def readConnectionLost(self):
        if (not self.sent_data):
            self.transport.write("hello\n")
            self.transport.loseConnection()

class TCP(protocol.Factory):
    """Dummy TCP server"""
    protocol = Echo

class QuickShutdownProtocol(protocol.Protocol):
    """Shuts down immediately after accepting"""
    def dataReceived(self, data):
        self.transport.loseConnection()

class QuickShutdown(protocol.Factory):
    protocol = QuickShutdownProtocol

class SMTPMessageParser(FeedParser):
    """Parse the email message and store the resulting MIME
    document in the original SMTP factory object."""

    implements(smtp.IMessage)

    def __init__(self, factory):
        self.factory = factory
        FeedParser.__init__(self)

    def lineReceived(self, line):
        self.feed("%s\n" % line)

    def eomReceived(self):
        self.factory.callback(self.close())
        return defer.succeed(None)

    def connectionLost(self):
        self.factory.callback(failure.Failure(error.ConnectionLost()))

class SMTPMessageDelivery(object):
    """Accept all messages"""

    implements(smtp.IMessageDelivery)

    def __init__(self, factory):
        self.factory = factory

    def receivedHeader(self, helo, origin, recipients):
        return "Received: Dummy SMTP Server"

    def validateFrom(self, helo, origin):
        return origin

    def validateTo(self, user):
        return lambda: SMTPMessageParser(self.factory)

class SMTP(smtp.SMTPFactory):

    def __init__(self):
        self.message = defer.Deferred()
        self.delivery = SMTPMessageDelivery(self)

    def buildProtocol(self, addr):
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.delivery = self.delivery
        return p

    def callback(self, result):
        self.message.callback(result)

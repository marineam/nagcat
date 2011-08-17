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

import os
import pwd
import time
import socket
from cStringIO import StringIO
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.generator import Generator

from zope.interface import classProvides
from twisted.internet import defer, reactor, task
from twisted.mail import smtp

from nagcat import notify


class PatientSMTPSenderFactory(smtp.SMTPSenderFactory):
    """The standard SMTPSender/SMTPSenderFactory pair will fire the
    deferred as soon as message sending is complete *OR* the connection
    was unexpectedly lost. Note that this means the deferred gets fired
    *BEFORE* the connection is closed if the send was successful. This
    makes for very grumpy unit tests and thus a very grumpy coder.
    """

    def __init__(self, fromEmail, toEmail, file, deferred,
                 retries=5, timeout=None):
        result = defer.Deferred()
        smtp.SMTPSenderFactory.__init__(self, fromEmail, toEmail, file,
                                        result, retries, timeout)
        self.connection_closed = deferred
        self.connection_closed.addBoth(lambda x: result)

    def _processConnectionError(self, connector, err):
        smtp.SMTPSenderFactory._processConnectionError(self, connector, err)
        self.connection_closed.callback(None)

def sendmail(smtphost, from_addr, to_addrs, msg,
             senderDomainName=None, port=25):
    """A copy/paste of smtp.sendmail() using PatientSMTPSenderFactory"""

    if not hasattr(msg,'read'):
        msg = StringIO(str(msg))

    d = defer.Deferred()
    factory = PatientSMTPSenderFactory(from_addr, to_addrs, msg, d)

    if senderDomainName is not None:
        factory.domain = senderDomainName

    reactor.connectTCP(smtphost, port, factory)

    return d


class EmailNotification(notify.Notification):
    """Send notifications via email"""

    classProvides(notify.INotification)

    name = "email"
    defaults = {'smtp': {'host': "127.0.0.1", 'port': 25}}

    def headers(self):
        local = time.localtime(int(self.macros['TIMET']))
        user = pwd.getpwuid(os.getuid())[0]
        host = socket.getfqdn()

        ret = {
            'Subject': self.subject(),
            'To': self.macros['CONTACTEMAIL'],
            'From': "%s@%s" % (user, host),
            'Date': smtp.rfc822date(local),
            'X-Nagios-Notification-Type': self.macros['NOTIFICATIONTYPE'],
            'X-Nagios-Host-Name': self.macros['HOSTNAME'],
            'X-Nagios-Host-State': self.macros['HOSTSTATE'],
            'X-Nagios-Host-Groups': self.macros['HOSTGROUPNAMES']
        }

        if self.type == "service":
            ret['X-Nagios-Service-Description'] = self.macros['SERVICEDESC']
            ret['X-Nagios-Service-State'] = self.macros['SERVICESTATE']
            ret['X-Nagios-Service-Groups'] = self.macros['SERVICEGROUPNAMES']

        return ret

    def body(self):
        text = super(EmailNotification, self).body()
        text += self.footer()
        return text

    def footer(self):
        urls = self.urls()

        if urls:
            text = "\n"
            if 'nagios' in urls:
                text += "Nagios: %s\n" % urls['nagios']
            if 'graphs' in urls:
                text += "Graphs: %s\n" % urls['graphs']
        else:
            text = ""

        return text

    def send(self):
        headers = self.headers()
        msg = MIMEMultipart()
        for key, value in headers.iteritems():
            msg[key] = value

        body = MIMEText(self.body())
        msg.attach(body)

        graph = self.graph()
        if graph:
            graph = MIMEImage(graph)
            graph.add_header('Content-Disposition',
                    'attachment', filename="graph.png")
            msg.attach(graph)

        coilcfg = self.coil()
        if coilcfg:
            coilcfg = MIMEText(coilcfg)
            coilcfg.add_header('Content-Disposition',
                    'attachment', filename="config.coil")
            msg.attach(coilcfg)

        msg_text = StringIO()
        gen = Generator(msg_text, mangle_from_=False)
        gen.flatten(msg)

        retry_limit = [notify.RETRY_LIMIT]
        def retry(result):
            retry_limit[0] -= 1
            if retry_limit[0] < 0:
                return result
            else:
                return task.deferLater(reactor,
                        notify.RETRY_INTERVAL, try_send)

        def try_send():
            msg_text.seek(0)
            deferred = sendmail(self.config['smtp.host'],
                    msg['From'], [msg['To']], msg_text,
                    port=self.config['smtp.port'])
            deferred.addErrback(retry)
            return deferred

        return try_send()


class PagerNotification(EmailNotification):

    classProvides(notify.INotification)

    name = "pager"
    format = "short"

    def headers(self):
        headers = super(PagerNotification, self).headers()
        headers['To'] = self.macros['CONTACTPAGER']
        return headers

    def footer(self):
        return ""

    def graph(self):
        return None

    def coil(self):
        return None

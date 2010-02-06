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
import sys
import pwd
import time
import socket
import urllib
from cStringIO import StringIO
from optparse import OptionParser
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.generator import Generator

from twisted.internet import reactor, task
from twisted.python import failure
from twisted.mail import smtp

import coil

from nagcat import log


# Attempt to retry after failures 6 times at 20 second intervals
RETRY_INTERVAL = 20
RETRY_LIMIT = 6

DEFAULT_CONFIG = '''
smtp: {
    host: "127.0.0.1"
}

urls: {
    nagios: None
    graphs: None
}

host: {
    subject: "{NOTIFICATIONTYPE} {HOSTNAME} is {HOSTSTATE}"

    long: {
        alert: """***** Nagios *****

        Type: {NOTIFICATIONTYPE}

        Host: {HOSTALIAS}
        Address: {HOSTADDRESS}
        State: {HOSTSTATE}
        Info: {HOSTOUTPUT}

        Date: {LONGDATETIME}
        """

        comment: """***** Nagios *****

        Type: {NOTIFICATIONTYPE}
        Author: {NOTIFICATIONAUTHOR}
        Comment: {NOTIFICATIONCOMMENT}

        Host: {HOSTALIAS}
        Address: {HOSTADDRESS}
        State: {HOSTSTATE}
        Info: {HOSTOUTPUT}

        Date: {LONGDATETIME}
        """
    }

    short: {
        alert: """Host {HOSTALIAS}
        Info: {HOSTOUTPUT}
        Date: {SHORTDATETIME}
        """

        comment: """Host {HOSTALIAS}
        Author: {NOTIFICATIONAUTHOR}
        Comment: {NOTIFICATIONCOMMENT}
        Date: {SHORTDATETIME}
        """
    }
}

service: {
    subject: "{NOTIFICATIONTYPE} {HOSTALIAS}/{SERVICEDESC} is {SERVICESTATE}"

    long: {
        alert: """***** Nagios *****

        Type: {NOTIFICATIONTYPE}

        Service: {SERVICEDESC}
        Host: {HOSTALIAS}
        Address: {HOSTADDRESS}
        State: {SERVICESTATE}
        Info: {SERVICEOUTPUT}
        {LONGSERVICEOUTPUT}

        Date: {LONGDATETIME}
        """

        comment: """***** Nagios *****

        Type: {NOTIFICATIONTYPE}
        Author: {NOTIFICATIONAUTHOR}
        Comment: {NOTIFICATIONCOMMENT}

        Service: {SERVICEDESC}
        Host: {HOSTALIAS}
        Address: {HOSTADDRESS}
        State: {SERVICESTATE}
        Info: {SERVICEOUTPUT}
        {LONGSERVICEOUTPUT}

        Date: {LONGDATETIME}
        """
    }

    short: {
        alert: """Service: {SERVICEDESC}
        Host: {HOSTALIAS}
        Info: {SERVICEOUTPUT}
        Date: {SHORTDATETIME}
        """

        comment: """Service: {SERVICEDESC}
        Host: {HOSTALIAS}
        Author: {NOTIFICATIONAUTHOR}
        Comment: {NOTIFICATIONCOMMENT}
        Date: {SHORTDATETIME}
        """
    }
}
'''

class MissingMacro(Exception):
    """A Nagios macro expected in the template is missing"""

    def __init__(self, name):
        super(MissingMacro, self).__init__("Missing Nagios macro: %s" % name)

class Macros(dict):

    def __getitem__(self, key):
        try:
            return super(Macros, self).__getitem__(key)
        except KeyError:
            raise MissingMacro(key)

class Notification(object):
    """Base notification class...."""

    format = "long"

    def __init__(self, type_, macros, config):
        assert type_ in ('host', 'service')
        self.type = type_
        self.macros = macros
        self.config = config

    def subject(self):
        return self._format(self.config[self.type]['subject'])

    def body(self):
        if (self.macros.get('NOTIFICATIONAUTHOR', None) or
                self.macros.get('NOTIFICATIONCOMMENT', None)):
            return self._format(self.config[self.type][self.format]['comment'])
        else:
            return self._format(self.config[self.type][self.format]['alert'])

    def urls(self):
        urls = {}
        if self.config['urls.nagios']:
            urls['nagios'] = \
                    "%s/cgi-bin/extinfo.cgi?type=2&host=%s&service=%s" % (
                    self.config['nagios_url'].rstrip("/"),
                    urllib.quote_plus(self.macros['HOSTNAME']),
                    urllib.quote_plus(self.macros['SERVICEDESC']))
        if self.config['urls.graphs']:
            urls['graphs'] = "%s/service.cgi?host=%s&service=%s" % (
                    self.config['graphs_url'].rstrip("/"),
                    urllib.quote_plus(self.macros['HOSTNAME']),
                    urllib.quote_plus(self.macros['SERVICEDESC']))
        return urls

    def graph(self):
        return None

    def coil(self):
        return None

    def send(self):
        pass

    def _format(self, text):
        text = "\n".join(l.strip() for l in text.splitlines())
        try:
            return text.format(**self.macros)
        except KeyError, ex:
            raise MissingMacro(ex.args[0])


class EmailNotification(Notification):

    def headers(self):
        local = time.localtime(int(self.macros['TIMET']))
        user = pwd.getpwuid(os.getuid())[0]
        host = socket.getfqdn()
        return {
            'Subject': self.subject(),
            'To': self.macros['CONTACTEMAIL'],
            'From': "%s@%s" % (user, host),
            'Date': smtp.rfc822date(local),
        }

    def body(self):
        text = super(EmailNotification, self).body()
        if self.format == "long":
            urls = self.urls()
            if urls:
                text += "\n"
                if 'nagios' in urls:
                    text += "Nagios: %s\n" % urls['nagios']
                if 'graphs' in urls:
                    text += "Graphs: %s\n" % urls['graphs']
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
            coilcfg = MIMEText(coil)
            coilcfg.add_header('Content-Disposition',
                    'attachment', filename="graph.png")
            msg.attach(coilcfg)

        msg_text = StringIO()
        gen = Generator(msg_text, mangle_from_=False)
        gen.flatten(msg)

        retry_limit = [RETRY_LIMIT]
        def retry(result):
            retry_limit[0] -= 1
            if retry_limit[0] < 0:
                return result
            else:
                return task.deferLater(reactor,
                        RETRY_INTERVAL, try_send)

        def try_send():
            msg_text.seek(0)
            deferred = smtp.sendmail(self.config['smtp.host'],
                    msg['From'], [msg['To']], msg_text)
            deferred.addErrback(retry)
            return deferred

        return try_send()


class PagerNotification(EmailNotification):

    format = "short"

    def headers(self):
        headers = super(PagerNotification, self).headers()
        headers['To'] = self.macros['CONTACTPAGER']

    def graph(self):
        return None

    def config(self):
        return None


def nagios_macros(environ):
    """Fetch the various Nagios macros from the environment.
    
    This allows notifications to use the macros as they would appear
    in Nagios config files which are a little shorter.
    """

    macros = Macros()

    for key, value in environ.iteritems():
        if not key.startswith("NAGIOS_"):
            continue
        key = key.replace("NAGIOS_", "", 1)
        if key.startswith("LONG") and key.endswith("OUTPUT"):
            value = value.replace(r'\n', '\n')
        macros[key] = value

    return macros

def parse_options():
    parser = OptionParser()
    parser.add_option("--email", action="store_true", default=False,
            help="send full email notice")
    parser.add_option("--pager", action="store_true", default=False,
            help="send shorter email notice for sms/pagers")
    parser.add_option("-H", "--host", action="store_true", default=False,
            help="this is a host notification")
    parser.add_option("-S", "--service", action="store_true", default=False,
            help="this is a service notification")
    parser.add_option("-c", "--config",
            help="load notification coil config")
    parser.add_option("-l", "--logfile",
            help="log errors to a given file")
    parser.add_option("-v", "--loglevel", default="WARN",
            help="set a specific log level")
    parser.add_option("-d", "--daemonize", action="store_true",
            help="daemonize to avoid blocking nagios")
    options, args = parser.parse_args()

    if args:
        parser.error("unknown extra arguments: %s" % args)

    if 1 != sum([options.email, options.pager]):
        parser.error("choose one and only one: email, pager")

    if 1 != sum([options.host, options.service]):
        parser.error("choose one and only one: host, service")

    if options.daemonize and not options.logfile:
        parser.error("--daemonize requires --log-file")

    return options

def main():
    options = parse_options()
    macros = nagios_macros(os.environ)

    log.init(options.logfile, options.loglevel)

    if options.daemonize:
        if os.fork() > 0:
            os._exit(0)
        os.chdir("/")
        os.setsid()
        if os.fork() > 0:
            os._exit(0)
        log.init_stdio()

    if not macros:
        log.error("No Nagios environment variables found.")
        sys.exit(1)

    try:
        config = coil.parse(DEFAULT_CONFIG)
        if options.config:
            config.merge(coil.parse_file(options.config))
    except coil.error.CoilError, ex:
        log.error("Error parsing config: %s" % ex)
        sys.exit(1)
    except IOError, ex:
        log.error("Error reading config file: %s" % ex)
        sys.exit(1)

    if options.host:
        event_type = "host"
    elif options.service:
        event_type = "service"
    else:
        assert 0

    if options.email:
        notifier = EmailNotification(event_type, macros, config)
    elif options.pager:
        notifier = PagerNotification(event_type, macros, config)
    else:
        assert 0

    exit_code = [-1]

    def start():
        try:
            deferred = notifier.send()
            deferred.addBoth(stop)
        except Exception:
            stop(failure.Failure())

    def stop(result):
        reactor.stop()
        if isinstance(result, failure.Failure):
            if isinstance(result.value, MissingMacro):
                log.error(str(result.value))
            else:
                log.error(str(result))
            exit_code[0] = 1
        else:
            exit_code[0] = 0

    reactor.callWhenRunning(start)
    reactor.run()
    sys.exit(exit_code[0])

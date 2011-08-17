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
import urllib
from optparse import OptionParser

from twisted.internet import reactor
from twisted.python import failure

import coil

from nagcat import errors, graph, log, plugin


# Attempt to retry after failures 6 times at 20 second intervals
RETRY_INTERVAL = 20
RETRY_LIMIT = 6

# Which template to use for each notification type
NOTIFICATION_TEMPLATES = {
    'alert': ('PROBLEM', 'RECOVERY'),
    'comment': ('ACKNOWLEDGEMENT', 'DOWNTIME', 'CUSTOM'),
    'flapping': ('FLAPPING',),
}

DEFAULT_CONFIG = '''
urls: {
    nagios: None
    graphs: None
}

rradir: None

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

        flapping: """***** Nagios *****

        Type: {NOTIFICATIONTYPE}

        No notifications are sent while the host state is flapping.

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

        flapping: """Host {HOSTALIAS}
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

        Date: {LONGDATETIME}
        """

        flapping: """***** Nagios *****

        Type: {NOTIFICATIONTYPE}

        No notifications are sent while the service state is flapping.

        Service: {SERVICEDESC}
        Host: {HOSTALIAS}
        Address: {HOSTADDRESS}
        State: {SERVICESTATE}
        Info: {SERVICEOUTPUT}

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

        flapping: """Service: {SERVICEDESC}
        Host: {HOSTALIAS}
        Date: {SHORTDATETIME}
        """
    }
}
'''

class NotificationError(Exception):
    """Generic known-error"""

class MissingMacro(NotificationError):
    """A Nagios macro expected in the template is missing"""

    def __init__(self, name):
        super(MissingMacro, self).__init__("Missing Nagios macro: %s" % name)

class Macros(dict):
    """Fetch the various Nagios macros from the environment.

    This allows notifications to use the macros as they would appear
    in Nagios config files which are a little shorter.

    Also provide a special Exception for missing macros.
    """

    def __init__(self, environ):
        for key, value in environ.iteritems():
            if not key.startswith("NAGIOS_"):
                continue
            key = key.replace("NAGIOS_", "", 1)
            if key.startswith("LONG") and key.endswith("OUTPUT"):
                value = value.replace(r'\n', '\n')
            self[key] = value

    def __getitem__(self, key):
        try:
            return super(Macros, self).__getitem__(key)
        except KeyError:
            raise MissingMacro(key)

class INotification(plugin.INagcatPlugin):
    """Interface provided by Notification plugin classes"""

class Notification(object):
    """Base notification class."""

    #: Name of this notification method
    name = None

    #: Format to use for generating text
    format = "long"

    #: Default config options for this class.
    #  (may be a string, dict, or Struct)
    defaults = {}

    def __init__(self, type_, macros, config):
        assert type_ in ('host', 'service')
        self.type = type_
        self.macros = macros
        self.config = config
        self.trend = None

        # Attempt to generate an rrdtool graph if this is a Nagcat service
        if (type_ == "service" and self.config['rradir']
                and self.macros.get('_SERVICETEST', None)):
            try:
                self.trend = graph.Graph(self.config['rradir'],
                        self.macros['HOSTNAME'],
                        self.macros['SERVICEDESC'])
            except errors.InitError, ex:
                log.warn("Unable to load RRDTool info for %s/%s: %s" %
                            (self.macros['HOSTNAME'],
                             self.macros['SERVICEDESC'], ex))

    def metadata(self, key, default=None):
        macro = key.upper()
        return self.macros.get('_CONTACT%s' % macro,
               self.macros.get('_SERVICE%s' % macro,
               self.macros.get('_HOST%s' % macro, default)))

    def subject(self):
        return self._format(self.config[self.type]['subject'])

    def body(self):
        for template, notification in NOTIFICATION_TEMPLATES.iteritems():
            if self.macros['NOTIFICATIONTYPE'].startswith(notification):
                return self._format(
                        self.config[self.type][self.format][template])

        raise NotificationError("Unknown notification type: %s" %
                                self.macros['NOTIFICATIONTYPE'])

    def urls(self):
        urls = {}
        if self.type == "host":
            if self.config['urls.nagios']:
                urls['nagios'] = \
                        "%s/cgi-bin/status.cgi?host=%s" % (
                        self.config['urls.nagios'].rstrip("/"),
                        urllib.quote_plus(self.macros['HOSTNAME']))
            if self.config['urls.graphs']:
                urls['graphs'] = "%s/host.cgi?host=%s" % (
                        self.config['urls.graphs'].rstrip("/"),
                        urllib.quote_plus(self.macros['HOSTNAME']))
        elif self.type == "service":
            if self.config['urls.nagios']:
                urls['nagios'] = \
                        "%s/cgi-bin/extinfo.cgi?type=2&host=%s&service=%s" % (
                        self.config['urls.nagios'].rstrip("/"),
                        urllib.quote_plus(self.macros['HOSTNAME']),
                        urllib.quote_plus(self.macros['SERVICEDESC']))
            if self.config['urls.graphs']:
                urls['graphs'] = "%s/service.cgi?host=%s&service=%s" % (
                        self.config['urls.graphs'].rstrip("/"),
                        urllib.quote_plus(self.macros['HOSTNAME']),
                        urllib.quote_plus(self.macros['SERVICEDESC']))
        else:
            assert 0
        return urls

    def graph(self):
        if self.trend:
            return self.trend.graph()
        else:
            return None

    def coil(self):
        if self.trend:
            return str(self.trend.conf)
        else:
            return None

    def send(self):
        raise Exception("unimplemented")

    def _format(self, text):
        text = "\n".join(l.strip() for l in text.splitlines())
        try:
            return text.format(**self.macros)
        except KeyError, ex:
            raise MissingMacro(ex.args[0])


def parse_options():
    notify_plugins = plugin.search(INotification)
    notify_list = ", ".join(notify_plugins)

    parser = OptionParser()
    parser.add_option("-m", "--method",
            help="notification method: %s" % notify_list)
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
    parser.add_option("-D", "--dump", action="store_true",
            help="just dump the config")
    options, args = parser.parse_args()

    if args:
        parser.error("unknown extra arguments: %s" % args)

    if not options.method:
        parser.error("--method is required")

    if options.method not in notify_plugins:
        parser.error("invalid method, choose from: %s" % notify_list)

    if not options.dump and 1 != sum([options.host, options.service]):
        parser.error("choose one and only one: host, service")

    if options.daemonize and not options.logfile:
        parser.error("--daemonize requires --log-file")

    return options, notify_plugins[options.method]

def main():
    options, method = parse_options()

    log.init(options.logfile, options.loglevel)

    if not options.dump and options.daemonize:
        if os.fork() > 0:
            os._exit(0)
        os.chdir("/")
        os.setsid()
        if os.fork() > 0:
            os._exit(0)
        log.init_stdio()

    try:
        config = coil.parse(DEFAULT_CONFIG)
        if method.defaults:
            if isinstance(method.defaults, str):
                config.merge(coil.parse(method.defaults))
            else:
                config.merge(coil.struct.Struct(method.defaults))
        if options.config:
            config.merge(coil.parse_file(options.config))
    except coil.errors.CoilError, ex:
        log.error("Error parsing config: %s" % ex)
        sys.exit(1)
    except IOError, ex:
        log.error("Error reading config file: %s" % ex)
        sys.exit(1)

    if options.dump:
        print str(config)
        sys.exit(0)

    macros = Macros(os.environ)
    if not macros:
        log.error("No Nagios environment variables found.")
        sys.exit(1)

    if options.host:
        event_type = "host"
    elif options.service:
        event_type = "service"
    else:
        assert 0

    notifier = method(event_type, macros, config)

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
            if isinstance(result.value, NotificationError):
                log.error(str(result.value))
            else:
                log.error(str(result))
            exit_code[0] = 1
        else:
            exit_code[0] = 0

    reactor.callWhenRunning(start)
    reactor.run()
    sys.exit(exit_code[0])

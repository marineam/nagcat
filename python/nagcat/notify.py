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

from zope.interface import Interface, Attribute, implements
from twisted.internet import reactor
from twisted.python import failure
from twisted.plugin import IPlugin, getPlugins

import coil

from nagcat import errors, log, trend, plugins


# Attempt to retry after failures 6 times at 20 second intervals
RETRY_INTERVAL = 20
RETRY_LIMIT = 6

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

class Notification(object):
    """Base notification class...."""

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
                self.trend = trend.Graph(self.config['rradir'],
                        self.macros['HOSTNAME'],
                        self.macros['SERVICEDESC'])
            except errors.InitError, ex:
                log.warn("Unable to load RRDTool info for %s/%s: %s" %
                            (self.macros['HOSTNAME'],
                             self.macros['SERVICEDESC'], ex))

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
        pass

    def _format(self, text):
        text = "\n".join(l.strip() for l in text.splitlines())
        try:
            return text.format(**self.macros)
        except KeyError, ex:
            raise MissingMacro(ex.args[0])


class INotificationFactory(Interface):
    """A factory for Notification objects."""

    name = Attribute("The name of this notification method")
    defaults = Attribute("Default coil configuration to add in")

    def notification(event_type, macros, config):
        """Create a new Notification object"""

class NotificationFactory(object):
    """Base class implementing INotificationFactory

    Since pretty much every plugin would wind up providing a nearly
    useless factory simply to conform to Twisted's plugin system we
    will provide a generic one everyone can use.
    """

    implements(IPlugin, INotificationFactory)

    def __init__(self, cls):
        self._cls = cls

    name = property(lambda self: self._cls.name)
    defaults = property(lambda self: self._cls.defaults)

    def notification(event_type, macros, config):
        return self._cls(event_type, macros, config)


def get_notify_plugins():
    """Find all notification plugins, return a dict"""
    return dict(dict((p.name, p) for p in
        getPlugins(INotificationFactory, plugins)))

def parse_options():
    notify_plugins = get_notify_plugins()
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
    options, plugin = parse_options()

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
        if plugin.defaults:
            if isinstance(plugin.defaults, str):
                config.merge(coil.parse(plugin.defaults))
            else:
                config.merge(coil.struct.Struct(plugin.defaults))
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

    notifier = plugin.notification(event_type, macros, config)

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

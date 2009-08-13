
import os
import signal
import warnings

from twisted.internet import defer, error, process, protocol, reactor
from twisted.python import log
from twisted.trial import unittest

from snapy import netsnmp

# Twisted falsely raises it's zombie warning
warnings.simplefilter("ignore", error.PotentialZombieWarning)

class LoggingProtocol(protocol.ProcessProtocol):
    """Log snmpd output via the twisted logging api"""

    def __init__(self, factory):
        self.factory = factory

    def outReceived(self, data):
        for line in data.splitlines():
            log.msg("snmpd: %s" % line)

    def errReceived(self, data):
        for line in data.splitlines():
            log.err("snmpd: %s" % line)

    def processEnded(self, status):
        if isinstance(status.value, error.ProcessDone):
            log.msg("snmpd: exit(0)")
            self.factory.done(None)
        elif isinstance(status.value, error.ProcessTerminated):
            log.err("snmpd: exit(%s)" % status.value.exitCode)
            self.factory.done(status)
        else:
            log.err("snmpd: %s" % status)
            self.factory.done(status)

class Server(process.Process):
    """Run snmpd"""

    def __init__(self):
        self._deferred = defer.Deferred()
        self._timeout = None
        self.conf = "%s/snmpd.conf" % os.path.dirname(__file__)
        self.port = 9999

        proto = LoggingProtocol(self)
        env = {"PATH": "/bin:/sbin:/usr/bin:/usr/sbin"}
        cmd = ("snmpd", "-f", "-C", "-c", self.conf,
                "127.0.0.1:%d" % self.port)
        super(Server, self).__init__(reactor, cmd[0], cmd, env, None, proto)

    def stop(self):
        assert self.pid and self._deferred
        os.kill(self.pid, signal.SIGTERM)
        self._timeout = reactor.callLater(1.0, self.timeout)
        return self._deferred

    def timeout(self):
        assert self.pid
        os.kill(self.pid, signal.SIGKILL)
        self._timeout = None

    def done(self, status):
        assert self._deferred

        if self._timeout:
            self._timeout.cancel()
            self._timeout = None

        self._deferred.callback(status)
        self._deferred = None

class TestCase(unittest.TestCase):

    version = "2c"

    def setUp(self):
        self.server = Server()
        self.session = netsnmp.Session("-v", self.version,
                "-c", "public", "127.0.0.1:%d" % self.server.port)
        self.session.open()

    def tearDown(self):
        self.session.close()
        return self.server.stop()

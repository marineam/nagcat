# snapy - a python snmp library
#
# Copyright (C) 2009 ITA Software, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# version 2 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import os
import socket
import signal
import warnings

from twisted.internet import defer, error, process, protocol, reactor
from twisted.python import log
from twisted.trial import unittest

def pick_a_port():
    # XXX: Not perfect, there is a race condition between
    # the close and snmpd's bind. However the other way
    # would be to hook into snmpd's bind() call...
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    host, port = sock.getsockname()
    sock.close()
    return port

class LoggingProtocol(protocol.ProcessProtocol):
    """Log snmpd output via the twisted logging api"""

    def __init__(self, factory):
        self.factory = factory

    def outReceived(self, data):
        for line in data.splitlines():
            log.msg("snmpd: %s" % line)

    def errReceived(self, data):
        for line in data.splitlines():
            if line.startswith("NET-SNMP"):
                self.factory.started()
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

    # Limit snmpd to only load these modules, this speeds things up
    modules = ('override', 'hr_system', 'system_mib')

    def __init__(self):
        self._deferred = defer.Deferred()
        self._address = defer.Deferred()
        self._timeout = None
        self.conf = "%s/snmpd.conf" % os.path.dirname(__file__)
        self.socket = "udp:127.0.0.1:%d" % pick_a_port()

        proto = LoggingProtocol(self)
        env = {"PATH": "/bin:/sbin:/usr/bin:/usr/sbin"}
        cmd = ("snmpd", "-f", "-LE6", "-C", "-c", self.conf,
                "-I", ','.join(self.modules),
                "--noPersistentLoad=1", "--noPersistentSave=1",
                self.socket)

        # Skip test if snmpd doesn't exist
        found = False
        for path in env['PATH'].split(':'):
            if os.path.exists("%s/%s" % (path, cmd[0])):
                found = True
                break
        if not found:
            raise unittest.SkipTest("snmpd missing")

        super(Server, self).__init__(reactor, cmd[0], cmd, env, None, proto)

    def started(self):
        log.msg("Ready, snmpd listening on %s" % self.socket)
        self._address.callback(self.socket)

    def address(self):
        return self._address

    def stop(self):
        assert self.pid and self._deferred
        log.msg("Stopping snmpd...")

        os.kill(self.pid, signal.SIGTERM)
        self._timeout = reactor.callLater(5.0, self.timeout)
        return self._deferred

    def timeout(self):
        assert self.pid
        log.msg("Timeout, Killing snmpd...")

        os.kill(self.pid, signal.SIGKILL)
        self._timeout = None

    def done(self, status):
        assert self._deferred

        if not self._address.called:
            self._address.errback(Exception("snmpd failed"))

        if self._timeout:
            self._timeout.cancel()
            self._timeout = None

        self._deferred.callback(status)
        self._deferred = None

class TestCase(unittest.TestCase):

    def setUp(self):
        # Twisted falsely raises it's zombie warning during tests
        warnings.simplefilter("ignore", error.PotentialZombieWarning)

        self.server = Server()
        d = self.server.address()
        d.addCallbacks(self.setUpSession, lambda x: None)
        d.addErrback(lambda x: self.server.stop())
        return d

    def setUpSession(self, address):
        pass

    def tearDown(self):
        try:
            self.tearDownSession()
        finally:
            d = self.server.stop()
        return d

    def tearDownSession(self):
        pass

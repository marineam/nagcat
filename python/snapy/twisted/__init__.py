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

from zope.interface import implements
from twisted.internet import defer, error, interfaces, reactor

from snapy import netsnmp

class SnmpReader(object):

    implements(interfaces.IReadDescriptor)

    def __init__(self, session):
        self._session = session

    def logPrefix(self):
        return self.__class__.__name__

    def fileno(self):
        return self._session.fileno()

    def doRead(self):
        return self._session.do_read()

    def connectionLost(self, reason):
        # TODO: How should we handle connection oriented protocols?
        # When using a Unix or TCP socket this may get triggered.
        # The API may need to be reworked again...
        pass

class Session(object):

    def __init__(self, **kwargs):
        self._session = netsnmp.Session(**kwargs)
        self._timeout = None
        self._reader = None

    def _do_timeout(self):
        self._timeout = None
        self._session.do_timeout()
        self._update_timeout()

    def _cancel_timeout(self):
        if self._timeout:
            self._timeout.cancel()
            self._timeout = None

    def _update_timeout(self):
        self._cancel_timeout()
        timeout = self._session.timeout()
        if timeout is not None:
            self._timeout = reactor.callLater(timeout, self._do_timeout)

    def open(self):
        self._session.open()
        self._reader = SnmpReader(self._session)
        reactor.addReader(self._reader)
        self._update_timeout()

    def close(self):
        self._cancel_timeout()
        reactor.removeReader(self._reader)
        self._reader = None
        self._session.close()

    def _done(self, result, deferred):
        def fire():
            self._update_timeout()
            if isinstance(result, netsnmp.SnmpTimeout):
                deferred.errback(error.TimeoutError())
            elif isinstance(result, Exception):
                deferred.errback(result)
            else:
                deferred.callback(result)

        # We must fire the deferred later because we don't want
        # to allow the user of this class to call any other
        # netsnmp functions while inside this netsnmp callback.
        reactor.callLater(0, fire)

    def get(self, oids):
        deferred = defer.Deferred()
        self._session.get(oids, self._done, deferred)
        self._update_timeout()
        return deferred

    def walk(self, oids, strict=False):
        deferred = defer.Deferred()
        self._session.walk(oids, self._done, deferred, strict=strict)
        self._update_timeout()
        return deferred

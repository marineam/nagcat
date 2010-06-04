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

"""The Twisted and Threaded part of this library!"""

import os
import stat

from twisted.internet import defer, error, reactor, threads

from twirrdy import RRDBasicAPI, RRDToolError
from twirrdy import protocol

def issock(path):
    mode = os.stat(path)[stat.ST_MODE]
    return stat.S_ISSOCK(mode)

class RRDTwistedAPI(RRDBasicAPI):
    """Wrapper around RRDBasicAPI that defers calls to threads.
    
    RRDTool updates are pretty quick operations but in an application
    that is making updates constantly they add up. A helpful solution
    is to defer the updates to the reactor's thread pool. Deferring
    calls to the thread pool is optional since that may not make sense
    in many situations.

    This class also supports sending updates via rrdcached.
    """

    def __init__(self, defer=True):
        """
        @param defer: Enable asyncronus calls by default
        """
        self._defer = defer
        self._client = None
        self.update = self._update_direct

    def open(self, address, pidfile=None):
        """Open connection to rrdcached

        @param address: path to rrdcached's UNIX socket
        @type address: str
        @param pidfile: optionally check rrdcached's pid file
        @type pidfile: str
        """

        deferred = defer.Deferred()
        self._client = protocol.RRDCacheClient(deferred)
        reactor.connectUNIX(address, self._client, checkPID=pidfile)
        self.update = self._update_cache
        return deferred

    def close(self):
        """Close connection to rrdcached"""

        def filter_done(result):
            if isinstance(result.value, error.ConnectionDone):
                return None
            else:
                return result

        assert self._client
        self._client.stopTrying()
        deferred = self._client.sendLine('QUIT')
        deferred.addErrback(filter_done)
        self._client = None
        self.update = self._update_direct
        return deferred

    def flush(self, filename):
        assert self._client
        filename = self._escape_filename(filename)
        return self._client.sendLine("FLUSH %s" % filename)

    def _escape_filename(self, filename):
        """Escape '\' and ' ' in file names"""
        return filename.replace('\\', '\\\\').replace(' ', '\\ ')

    def _update_cache(self, filename, timestamp, values, defer=None):
        """Update via rrdcached"""

        if defer is None:
            defer = self._defer

        if not defer:
            super(RRDTwistedAPI, self).update(filename, timestamp, values)
        else:
            assert self._client
            filename = self._escape_filename(filename)
            # format: UPDATE filename.rrd time:v1:v2:...
            line = "UPDATE %s %s:%s" % (filename, int(timestamp),
                    ':'.join(str(v) for v in values))
            return self._client.sendLine(line)

    def _update_direct(self, filename, timestamp, values, defer=None):
        """Update via library call"""

        if defer is None:
            defer = self._defer

        doupdate = lambda: super(RRDTwistedAPI, self).update(
                    filename, timestamp, values)
        if not defer:
            doupdate()
        else:
            return threads.deferToThread(doupdate)

    def create(self, filename, ds, rra, step=300, start=None, defer=None):
        if defer is None:
            defer = self._defer

        docreate = lambda: super(RRDTwistedAPI, self).create(
                    filename, ds, rra, step, start)
        if not defer:
            docreate()
        else:
            return threads.deferToThread(docreate)

    def info(self, filename, defer=None):
        if defer is None:
            defer = self._defer

        doinfo = lambda: super(RRDTwistedAPI, self).info(filename)

        if not defer:
            return doinfo()
        else:
            if self._client:
                deferred = self.flush(filename)
                deferred.addCallback(lambda x: threads.deferToThread(doinfo))
                return deferred
            else:
                return threads.deferToThread(doinfo)

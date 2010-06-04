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

from twisted.internet import threads

from twirrdy import RRDBasicAPI, RRDToolError

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

    def __init__(self, rrdcached_address=None):
        """Only UNIX sockets are supported at the moment"""

        if rrdcached_address:
            if not issock(rrdcached_address):
                raise RRDToolError("rrdcached_address is not a UNIX socket")

            self._rrdcached_address = rrdcached_address
            self.update = self._update_cache
        else:
            self.update = self._update_direct

    def _update_cache(self, filename, timestamp, values, defer=True):
        """Update via rrdcached"""
        if not defer:
            super(RRDTwistedAPI, self).update(filename, timestamp, values)
        else:
            pass

    def _update_direct(self, filename, timestamp, values, defer=True):
        """Update via library call"""
        if not defer:
            super(RRDTwistedAPI, self).update(filename, timestamp, values)
        else:
            return threads.deferToThread(
                    super(RRDTwistedAPI, self).update,
                    filename, timestamp, values)

    def info(self, filename, defer=True):
        if not defer:
            return super(RRDTwistedAPI, self).info(filename)
        else:
            return threads.deferToThread(
                    super(RRDTwistedAPI, self).info, filename)

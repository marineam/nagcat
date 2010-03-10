# Copyright 2008-2010 ITA Software, Inc.
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

"""HTTP Queries"""

import urlparse
from base64 import b64encode

from zope.interface import classProvides
from twisted.internet import reactor, defer
from twisted.internet import error as neterror
from twisted.web import error as weberror
from twisted.web.client import HTTPClientFactory
from twisted.python.util import InsensitiveDict

try:
    import uuid
except ImportError:
    uuid = None

# SSL support is screwy
try:
   from twisted.internet import ssl
except ImportError:
   # happens the first time the interpreter tries to import it
   ssl = None
if ssl and not ssl.supported:
   # happens second and later times
   ssl = None

from nagcat import errors, query


class HTTPQuery(query.Query):
    """Process an HTTP GET or POST"""

    classProvides(query.IQuery)

    name = "http"
    port = 80

    def __init__(self, conf):
        super(HTTPQuery, self).__init__(conf)

        self.agent = "NagCat" # Add more info?
        self.scheme = self.name
        self.conf['addr'] = self.addr
        self.conf['port'] = int(conf.get('port', self.port))
        self.conf['path'] = conf.get('path', '/')
        self.conf['data'] = conf.get('data', None)
        headers = conf.get('headers', {})

        # Some versions of twisted will send Host twice if it is in the
        # headers dict. Instead we set factory.host.
        if self.conf['port'] == self.port:
            self.headers_host = self.host
        else:
            self.headers_host = "%s:%s" % (self.host, self.conf['port'])

        # We need to make sure headers is a dict.
        self.headers = InsensitiveDict()
        for (key, val) in headers.iteritems():
            if key.lower() == 'host':
                self.headers_host = val
            else:
                self.headers[key] = val

        # Set the Authorization header if user/pass are provided
        user = conf.get('username', None)
        if user is not None:
            auth = b64encode("%s:%s" % (user, conf['password']))
            self.headers['Authorization'] = "Basic %s" % auth

        # Also convert to a lower-case only dict for self.conf so
        # that queries that differ only by case are still shared.
        self.conf['headers'] = InsensitiveDict(preserve=0)
        self.conf['headers']['host'] = self.headers_host
        self.conf['headers'].update(self.headers)

        if self.conf['data']:
            self.method = "POST"
        else:
            self.method = "GET"

        self.request_url = urlparse.urlunsplit((self.scheme,
                self.headers_host, self.conf['path'], None, None))

    def _start(self):
        # Generate a request id if possible
        if uuid:
            self.request_id = str(uuid.uuid1())
            self.headers['X-Request-Id'] = self.request_id

        factory = HTTPClientFactory(url=self.conf['path'],
                method=self.method, postdata=self.conf['data'],
                headers=self.headers, agent=self.agent,
                timeout=self.conf['timeout'], followRedirect=0)
        factory.host = self.headers_host
        factory.noisy = False
        factory.deferred.addErrback(self._failure_tcp)
        factory.deferred.addErrback(self._failure_http)
        self._connect(factory)
        return factory.deferred

    @errors.callback
    def _failure_http(self, result):
        """Convert HTTP specific failures to a TestError"""

        if isinstance(result.value, defer.TimeoutError):
            raise errors.TestCritical("Timeout waiting on HTTP response")

        elif isinstance(result.value, neterror.ConnectionDone):
            raise errors.TestCritical("Empty HTTP Response")

        elif isinstance(result.value, weberror.PageRedirect):
            # Redirects aren't actually an error :-)
            result = "%s\n%s" % (result.value, result.value.location)

        elif isinstance(result.value, weberror.Error):
            raise errors.TestCritical("HTTP error: %s" % result.value)

        return result

    def _connect(self, factory):
        # Split out the reactor.connect call to allow for easy
        # overriding in HTTPSQuery
        reactor.connectTCP(self.addr, self.conf['port'],
                factory, self.conf['timeout'])


class HTTPSQuery(HTTPQuery):
    """Process an HTTP GET or POST over SSL"""

    classProvides(query.IQuery)

    name = "https"
    port = 443

    def __init__(self, conf):
        if ssl is None:
            raise errors.InitError("pyOpenSSL is required for HTTPS support.")
        super(HTTPSQuery, self).__init__(conf)

    def _connect(self, factory):
        context = ssl.ClientContextFactory()
        reactor.connectSSL(self.addr, self.conf['port'],
                factory, context, self.conf['timeout'])

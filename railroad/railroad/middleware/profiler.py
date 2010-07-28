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

# Based on this snippet: http://djangosnippets.org/snippets/1579/

import cProfile
import os
#import pstats
import tempfile
from cStringIO import StringIO

from django.conf import settings

class ProfilerMiddleware(object):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        if settings.DEBUG and 'prof' in request.GET:
            self.profiler = cProfile.Profile()
            args = (request,) + callback_args
            return self.profiler.runcall(callback, *args, **callback_kwargs)

    def process_response(self, request, response):
        if settings.DEBUG and 'prof' in request.GET:
            (fd, self.profiler_file) = tempfile.mkstemp()
            self.profiler.dump_stats(self.profiler_file)
#            out = StringIO()
#            stats = pstats.Stats(self.profiler_file, stream=out)
#            stats.strip_dirs()          # Must happen prior to sort_stats
#            if request.GET['prof']:
#                stats.sort_stats(request.GET['prof'])
#            stats.print_stats()
#            os.unlink(self.profiler_file)
#            response.content = '<pre>%s</pre>' % out.getvalue()
            f = open(self.profiler_file)
            response.content = f.read()
            response['Content-Type'] = 'application/octet-stream'
        return response

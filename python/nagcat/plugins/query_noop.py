# Copyright 2009-2010 ITA Software, Inc.
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

"""No-Op Query"""

from zope.interface import classProvides
from twisted.internet import defer
from nagcat import query

class NoopQuery(query.Query):
    """Dummy query useful for testing."""

    classProvides(query.IQuery)

    name = "noop"

    def __init__(self, nagcat, conf):
        super(NoopQuery, self).__init__(nagcat, conf)
        self.conf['data'] = conf.get('data', None)

    def _start(self):
        return defer.succeed(self.conf['data'])

# Copyright 2009-2011 ITA Software, Inc.
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

"""Nagios Status Query"""

from zope.interface import classProvides
from nagcat import errors, query

try:
    from lxml import etree
except ImportError:
    etree = None

class HostQuery(query.Query):
    """Get service status info out of Nagios"""

    classProvides(query.IQuery)

    name = "host_status"
    _obj_type = "host"

    def __init__(self, nagcat, conf):
        super(HostQuery, self).__init__(nagcat, conf)
        self.conf['attribute'] = conf.get('attribute', None)
        self._nagcat = nagcat
        assert self.host

        if not hasattr(nagcat, "nagios_status"):
            # FIXME
            raise errors.InitError("boo lame")

        if not self.conf['attribute'] and not etree:
            raise errors.InitError("lxml is required!")

    def _nagios_select(self):
        status = self._nagcat.nagios_status()
        found = None
        for host in status['host']:
            if (host['host_name'] == self.host):
                found = host
                break

        if not found:
            raise errors.TestCritical("No such host %s/%s" % (self.host,))

        return found

    def _start(self):
        nagios_obj = self._nagios_select()

        if self.conf['attribute']:
            try:
                return nagios_obj[self.conf['attribute']]
            except KeyError:
                raise errors.TestCritical(
                        "No such attribute %s" % (self.conf['attribute'],))
        else:
            return self._nagios_to_xml(nagios_obj)

    def _nagios_to_xml(self, nagios_obj):
        root = etree.Element(self._obj_type)
        for key, value in nagios_obj.iteritems():
            # Skip custom attributes for a few reasons:
            # - their names may not be valid for XML
            # - the user probably expects them to appear as they did in
            #   original object definition but in the status the names
            #   are forced to uppercase and the data starts with 0;
            # - they aren't dynamic so why would they be tested anyway?
            if key.startswith('_'):
                continue
            new = etree.Element(key)
            new.text = value
            root.append(new)
        return etree.tostring(root, pretty_print=True)

class ServiceQuery(HostQuery):
    """Get host status info out of Nagios"""

    classProvides(query.IQuery)

    name = "service_status"
    _obj_type = "service"

    def __init__(self, nagcat, conf):
        super(ServiceQuery, self).__init__(nagcat, conf)
        self.conf['description'] = conf.get('description')

    def _nagios_select(self):
        status = self._nagcat.nagios_status()
        found = None
        for service in status['service']:
            if (service['service_description'] == self.conf['description']
                    and service['host_name'] == self.host):
                found = service
                break

        if not found:
            raise errors.TestCritical("No such service %s/%s" %
                    (self.host, self.conf['description']))

        return found

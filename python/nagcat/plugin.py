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

from zope.interface import Attribute
from twisted.plugin import IPlugin, getPlugins

from nagcat import plugins

class INagcatPlugin(IPlugin):
    """Interface for Nagcat plugin classes, should be sub-classed"""

    name = Attribute("Name of this plugin")

_missing = object()
def search(interface, name=None, default=_missing):
    """Search for a plugin providing a given interface.

    If name is provided return the specific plugin, otherwise
    return a dict containing everything providing the interface.
    """

    assert issubclass(interface, INagcatPlugin)

    found = {}
    for cls in getPlugins(interface, plugins):
        if cls.name is None:
            continue
        else:
            found[cls.name] = cls

    if name:
        if default is not _missing:
            return found.get(name, default)
        else:
            return found[name]
    else:
        return found

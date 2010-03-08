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

from zope.interface import Interface, Attribute, implements
from twisted.plugin import IPlugin, getPlugins

from nagcat import plugins

class INagcatPlugin(Interface):
    """Interface used to find plugin classes"""

    name = Attribute("Name of this plugin")

class NagcatPlugin(type):
    """Metaclass implementing INagcatPlugin for plugin classes.
    
    The Twisted plugin system searches for objects that are instances
    of a class implementing a particular Interface. Using a metaclass
    allows us to find classes based on this search system rather than
    the objects themselves.
    """

    implements(IPlugin, INagcatPlugin)

    # plugin classes should provide this.
    name = None

def search(base_class):
    found = {}
    for cls in getPlugins(INagcatPlugin, plugins):
        if issubclass(cls, base_class):
            if cls.name is None:
                continue
            else:
                found[cls.name] = cls
    return found

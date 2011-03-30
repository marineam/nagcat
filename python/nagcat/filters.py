# Copyright 2008-2009 ITA Software, Inc.
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

"""Data filters used by Test objects"""

import re

from nagcat import errors, plugin

# Accept filter specs in the format "name[default]:arguments"
# where [default] and :arguments are optional
_SPEC = re.compile(r'^([a-z][a-z0-9]*)(\[([^\]]*)\])?(:)?')

def Filter(test, spec):
    """Factory that creates a Filter object from the spec"""

    assert isinstance(spec, str)

    match = _SPEC.match(spec)
    if not match:
        raise errors.InitError("Invalid filter spec: '%s'" % spec)

    name = match.group(1)
    default = match.group(3)

    if match.group(4):
        arguments = spec[match.end():]
    else:
        arguments = ""

    return get_filter(test, name, default, arguments)

def get_filter(test, name, default, arguments):
    """Search the plugins for the requested filter and create it"""

    filter_class = plugin.search(IFilter, name, None)
    if filter_class:
        assert issubclass(filter_class, _Filter)
        return filter_class(test, default, arguments)
    else:
        raise errors.InitError("Invalid filter type '%s'" % name)

class IFilter(plugin.INagcatPlugin):
    """Interface for finding Filter plugins"""

class _Filter(object):
    """Filter class template"""

    # Set whether this filter allows default values
    handle_default = True
    # Set whether this filter accepts arguments
    handle_arguments = True
    # Set weather this filter should be on the errorback chain
    # in addition to the normal callback chain.
    handle_errors = False

    def __init__(self, test, default, arguments):
        self.test = test
        self.default = default
        self.arguments = arguments

        if not self.handle_default and self.default is not None:
            raise errors.InitError("'%s' filters cannot take default values"
                    % self.__class__.__name__.replace("Filter_",""))

        if not self.handle_arguments and self.arguments:
            raise errors.InitError("'%s' filters cannot take arguments"
                    % self.__class__.__name__.replace("Filter_",""))

    @errors.callback
    def filter(self, result):
        """Run the filter on the given input.

        All filters must expect and return a str.
        """
        raise Exception("Unimplemented!")

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

"""snappy - a python snmp library

Snappy provides some basic python bindings for netsnmp as well as a
Twisted interface. It is based in part on the pynetsnmp library by
Zenoss but has been diverged significantly to simplify the API and
improve performance and reliability.
"""

__version_info__ = (0,1,0)
__version__ = ".".join([str(x) for x in __version_info__])
__all__ = ('netsnmp', 'twisted')

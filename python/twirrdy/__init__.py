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

"""A Twisted (and thread safe) RRDTool library"""

import os
import ctypes

# OrderedDict isn't available till 2.7
try:
    from collections import OrderedDict
except ImportError:
    from twirrdy.ordereddict import OrderedDict

try:
    rrd_th = ctypes.CDLL("librrd_th.so", ctypes.RTLD_GLOBAL)
except OSError:
    raise ImportError("Unable to load librrd_th.so")

c_char_pp = ctypes.POINTER(ctypes.c_char_p)

rrd_th.rrd_get_error.argtypes = []
rrd_th.rrd_get_error.restype = ctypes.c_char_p
rrd_th.rrd_clear_error.argtypes = []
rrd_th.rrd_clear_error.restype = None

rrd_th.rrd_update_r.argtypes = [
        ctypes.c_char_p,    # filename
        ctypes.c_char_p,    # template
        ctypes.c_int,       # argc
        c_char_pp]          # argv
rrd_th.rrd_update_r.restype = ctypes.c_int

rrd_info_type_t = ctypes.c_int
(RD_I_VAL,
 RD_I_CNT,
 RD_I_STR,
 RD_I_INT,
 RD_I_BLO) = xrange(5)

rrd_value_t = ctypes.c_double

class rrd_blob_t(ctypes.Structure):
    _fields_ = [
        ('size', ctypes.c_ulong),
        ('ptr', ctypes.c_void_p)]

class rrd_infoval_t(ctypes.Union):
    _fields_ = [
        ('u_cnt', ctypes.c_ulong),
        ('u_val', rrd_value_t),
        ('u_str', ctypes.c_char_p),
        ('u_int', ctypes.c_int),
        ('u_blo', rrd_blob_t)]

class rrd_info_t(ctypes.Structure):
    pass
rrd_info_t._fields_ = [
        ('key', ctypes.c_char_p),
        ('type', rrd_info_type_t),
        ('value', rrd_infoval_t),
        ('next', ctypes.POINTER(rrd_info_t))]

# Some versions of rrdtool don't export rrd_info_r,
# but in those versions rrd_info is thread safe.
if hasattr(rrd_th, 'rrd_info_r'):
    rrd_th.rrd_info_r.argtypes = [ ctypes.c_char_p ]
    rrd_th.rrd_info_r.restype = ctypes.POINTER(rrd_info_t)
    rrd_info_r = rrd_th.rrd_info_r
else:
    rrd_th.rrd_info.argtypes = [ ctypes.c_int, c_char_pp ]
    rrd_th.rrd_info.restype = ctypes.POINTER(rrd_info_t)
    def rrd_info_r(filename):
        argv_t = ctypes.c_char_p * 2
        argv = argv_t("", filename)
        return rrd_th.rrd_info(2, argv)


class RRDToolError(Exception):
    """General RRDTool Error"""

class RRDLibraryError(RRDToolError):
    """Errors reported by function calls"""

    def __init__(self):
        error = str(rrd_th.rrd_get_error())
        Exception.__init__(self, error)
        rrd_th.rrd_clear_error()

class RRDBasicAPI(object):
    """Basic RRDTool API - threadsafe and doesn't require Twisted"""

    def update(self, filename, timestamp, values):
        """Update the given file with a list of values.
        
        Note: templates are not supported because the cache
        protocol does not support them.
        """
        if not os.path.exists(filename):
            raise RRDToolError("%s does not exist" % filename)

        arg = "%s:%s" % (timestamp, ":".join(str(v) for v in values))
        argv_t = ctypes.c_char_p * 1
        argv = argv_t(arg)
        if rrd_th.rrd_update_r(filename, None, 1, argv):
            raise RRDLibraryError()

    def info(self, filename):
        """Get the information structure for a file.

        This is different from rrdtool.info() in that it uses ordered
        dicts to return the ds list. This is important because the
        cache protocol doesn't support templates so the order we send
        values in is significant. Yay.

        rra[].cdp_prep values are currently ignored.
        """

        ptr = rrd_info_r(filename)
        if not ptr:
            raise RRDLibraryError()

        def value(value):
            if value.type == RD_I_VAL:
                # Replace NaN with None
                if value.value.u_val != value.value.u_val:
                    return None
                else:
                    return float(value.value.u_val)
            elif value.type == RD_I_CNT:
                return int(value.value.u_cnt)
            elif value.type == RD_I_STR:
                return str(value.value.u_str)
            elif value.type == RD_I_INT:
                return str(value.value.u_int)
            else:
                # RD_I_BLO or anything else shouldn't happen.
                raise RRDToolError("Unexpected data type %s" % value.type)

        def ds_key(name):
            # ds[total].index
            return name[3:].split('].', 1)

        def rra_key(name):
            # rra[0].cf
            index, key = name[4:].split('].', 1)
            return int(index), key

        ret = {}
        ret['ds'] = OrderedDict()
        ret['rra'] = []
        while ptr:
            this = ptr.contents
            if this.key.startswith('ds['):
                name, key = ds_key(this.key)
                if name not in ret['ds']:
                    ret['ds'][name] = {key: value(this)}
                else:
                    ret['ds'][name][key] = value(this)
            elif this.key.startswith('rra['):
                index, key = rra_key(this.key)
                if key.startswith('cdp_prep['):
                    pass
                elif len(ret['rra']) != index+1:
                    ret['rra'].append({key: value(this)})
                else:
                    ret['rra'][index][key] = value(this)
            else:
                ret[str(this.key)] = value(this)
            ptr = this.next

        return ret

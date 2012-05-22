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

import time
import ctypes

# OrderedDict isn't available till 2.7
try:
    from collections import OrderedDict
except ImportError:
    from twirrdy.ordereddict import OrderedDict

# Try loading without find_library first so RPATH is respected.
# RPATH is needed for some of my stuff but find_library is needed
# almost everywhere else. Maybe someday I'll fix find_library...
try:
    rrd_th = ctypes.CDLL("librrd_th.so", ctypes.RTLD_GLOBAL)
except OSError:
    from ctypes.util import find_library
    rrd_th_name = find_library("rrd_th")
    if not rrd_th_name:
        raise ImportError("Unable to load RRDTool library rrd_th")
    rrd_th = ctypes.CDLL(rrd_th_name, ctypes.RTLD_GLOBAL)

rrd_th.rrd_version.argtypes = []
rrd_th.rrd_version.restype = ctypes.c_double
rrd_version = rrd_th.rrd_version()
if rrd_version < 1.3:
    raise ImportError("RRDTool version >= 1.3 is required")

# some handy types
c_time_t = ctypes.c_long
c_char_pp = ctypes.POINTER(ctypes.c_char_p)
raw_char_p = ctypes.POINTER(ctypes.c_char)
raw_char_pp = ctypes.POINTER(raw_char_p)

rrd_th.rrd_get_error.argtypes = []
rrd_th.rrd_get_error.restype = ctypes.c_char_p
rrd_th.rrd_clear_error.argtypes = []
rrd_th.rrd_clear_error.restype = None

rrd_th.rrd_create_r.argtypes = [
        ctypes.c_char_p,    # filename
        ctypes.c_ulong,     # step
        c_time_t,           # start
        ctypes.c_int,       # argc
        c_char_pp]          # argv

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

# Versions less that 1.4 don't provide/export *_r versions of some
# functions but in those cases the non *_r version is thread safe.
if rrd_version >= 1.4:
    rrd_th.rrd_info_r.argtypes = [ ctypes.c_char_p ]
    rrd_th.rrd_info_r.restype = ctypes.POINTER(rrd_info_t)
    rrd_info_r = rrd_th.rrd_info_r

    # note: raw_char_pp is required so free() works
    rrd_th.rrd_lastupdate_r.argtypes = [
            ctypes.c_char_p,                # filename
            ctypes.POINTER(c_time_t),       # ret_last_update
            ctypes.POINTER(ctypes.c_ulong), # ret_ds_count
            ctypes.POINTER(raw_char_pp),    # ret_ds_names
            ctypes.POINTER(raw_char_pp)]    # ret_last_ds
    rrd_th.rrd_lastupdate_r.restype = ctypes.c_int
    rrd_lastupdate_r = rrd_th.rrd_lastupdate_r

else:
    rrd_th.rrd_info.argtypes = [ ctypes.c_int, c_char_pp ]
    rrd_th.rrd_info.restype = ctypes.POINTER(rrd_info_t)
    def rrd_info_r(filename):
        argv_t = ctypes.c_char_p * 2
        argv = argv_t("", filename)
        return rrd_th.rrd_info(2, argv)

    rrd_th.rrd_lastupdate.argtypes = [
            ctypes.c_int,                   # argc
            c_char_pp,                      # argv
            ctypes.POINTER(c_time_t),       # ret_last_update
            ctypes.POINTER(ctypes.c_ulong), # ret_ds_count
            ctypes.POINTER(raw_char_pp),    # ret_ds_names
            ctypes.POINTER(raw_char_pp)]    # ret_last_ds
    rrd_th.rrd_lastupdate.restype = ctypes.c_int
    def rrd_lastupdate_r(filename, last_update, ds_count, ds_names, last_ds):
        argv_t = ctypes.c_char_p * 2
        argv = argv_t("", filename)
        return rrd_th.rrd_lastupdate(2, argv,
                last_update, ds_count, ds_names, last_ds)


rrd_th.rrd_info_free.argtypes = [ ctypes.POINTER(rrd_info_t) ]
rrd_th.rrd_info_free.restype = None
rrd_th.rrd_freemem.argtypes = [ ctypes.c_void_p ]
rrd_th.rrd_freemem.restype = None


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

    def create(self, filename, ds, rra, step=300, start=None):
        """Create a new RRDTool database.

        COMPUTE data sources and predictive rras aren't supported.

        @param filename: Path to new file, must not exist.
        @type filename: str
        @param ds: list or dict of dicts defining data sources:
            {'name': data source name, not required for dicts of dicts
             'type': "GAGUE" or "COUNTER" or "DERIVE" or "ABSOLUTE",
             'heartbeat': int, # 'minimal_heartbeat' is also accepted
             'min': float or None, # defaults to None
             'max': float or None} # defaults to None
        @param rra: list of dicts defining rras:
            {'cf': "AVERAGE" or "MIN" or "MAX" or "LAST",
             'xff': float,
             'pdp_per_row': int,
             'rows': int}
        @param step: data feeding rate in seconds
        @type step: int
        @param start: start time in seconds, defaults to time() - 10
        @time start: int or None
        """

        args = []
        step = int(step)
        if not start:
            start = time.time() - 10
        else:
            start = int(start)

        def check_minmax(item, key):
            value = item.get(key, None)
            if value is None:
                item[key] = 'U'
            else:
                item[key] = int(value)

        def add_ds(item, name=None):
            item = item.copy()
            if name is not None:
                item.setdefault('name', name)
            if 'minimal_heartbeat' not in item:
                item['minimal_heartbeat'] = item['heartbeat']
            check_minmax(item, 'min')
            check_minmax(item, 'max')
            assert ':' not in item['name']
            args.append(("DS:%(name)s:%(type)s:"
                "%(minimal_heartbeat)d:%(min)s:%(max)s") % item)

        if hasattr(ds, 'iteritems'):
            for name, item in ds.iteritems():
                add_ds(item, name)
        else:
            for item in ds:
                add_ds(item)

        for item in rra:
            args.append("RRA:%(cf)s:%(xff)f:%(pdp_per_row)d:%(rows)d" % item)

        argc = len(args)
        argv_t = ctypes.c_char_p * argc
        argv = argv_t(*args)
        if rrd_th.rrd_create_r(filename, step, start, argc, argv):
            raise RRDLibraryError()

    def update(self, filename, timestamp, values):
        """Update the given file with a list of values.
        
        Note: templates are not supported because the cache
        protocol does not support them.
        """

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

        ptr = info_ptr = rrd_info_r(filename)
        if not ptr:
            raise RRDLibraryError()

        try:
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
        finally:
            rrd_th.rrd_info_free(info_ptr)

        return ret

    def lastupdate(self, filename):
        """Get the latest update from an RRD

        It is basically a mini info()
        """

        ds_time = c_time_t()
        ds_count = ctypes.c_ulong()
        ds_names = raw_char_pp()
        ds_values = raw_char_pp()
        if rrd_lastupdate_r(filename,
                ctypes.byref(ds_time),
                ctypes.byref(ds_count),
                ctypes.byref(ds_names),
                ctypes.byref(ds_values)):
            raise RRDLibraryError()

        ds_dict = OrderedDict()
        for i in xrange(int(ds_count.value)):
            name = ctypes.string_at(ds_names[i])
            value = ctypes.string_at(ds_values[i])
            if value == "U":
                value = None
            else:
                value = float(value)
            ds_dict[name] = value
            rrd_th.rrd_freemem(ds_values[i])
            rrd_th.rrd_freemem(ds_names[i])

        rrd_th.rrd_freemem(ds_values)
        rrd_th.rrd_freemem(ds_names)

        return ds_time.value, ds_dict

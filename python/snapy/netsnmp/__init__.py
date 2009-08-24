# snapy - a python snmp library
#
# Copyright (C) 2009 ITA Software, Inc.
# Copyright (c) 2007 Zenoss, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# version 2 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import sys
import math
import select
import ctypes
from ctypes import byref
from ctypes.util import find_library

lib = ctypes.CDLL(find_library('netsnmp'), ctypes.RTLD_GLOBAL)

from snapy.netsnmp import const, types, util

"""Net-SNMP bindings for the single session API"""

class SnmpError(Exception):
    """Error in NetSNMP"""
    pass

class SnmpTimeout(Exception):
    """SNMP Timeout"""
    def __init__(self):
        super(SnmpTimeout, self).__init__(self.__class__.__doc__)

# The normal fd limit
FD_SETSIZE = 1024

def _mkfdset(fd):
    """Make a fd set of the right size and set fd"""
    size = max(fd, FD_SETSIZE)
    fd_set_t = ctypes.c_int32 * int(math.ceil(size / 32.0))
    fd_set = fd_set_t()
    fd_set[fd // 32] |= 1 << (fd % 32)
    return fd_set

def _parse_args(args, session):
    """Wrapper around snmp_parse_args"""

    @types.snmp_parse_args_proc
    def dummy(argc, argv, arg):
        pass

    args = ["snapy"] + list(args)
    argc = len(args)
    argv = (ctypes.c_char_p * argc)()

    for i, arg in enumerate(args):
        argv[i] = ctypes.create_string_buffer(arg).raw

    err = lib.snmp_parse_args(argc, argv, byref(session), '', dummy)
    if err < 0:
        raise SnmpError("snmp_parse_args: %d" % err)

    # keep a reference to argv while session is alive
    return argv

class Session(object):
    """Wrapper around a single SNMP Session"""

    def __init__(self, *args):
        # TODO: support kwargs?
        self.sessp = None   # single session api pointer
        self.session = None # session struct
        self.session_template = types.netsnmp_session()
        self._requests = None

        self._session_argv = _parse_args(args, self.session_template)
        self.session_template.callback = types.netsnmp_callback(self._callback)

    def error(self):
        pass

    def open(self):
        sess = types.netsnmp_session()
        ctypes.memmove(byref(sess),
                byref(self.session_template), ctypes.sizeof(sess))

        self.sessp = lib.snmp_sess_open(byref(sess))
        if not self.sessp:
            raise SnmpError('snmp_sess_open')

        self.session = lib.snmp_sess_session(self.sessp)
        self._requests = {}

    def close(self):
        assert self.sessp
        lib.snmp_sess_close(self.sessp)
        self.sessp = None
        self.session = None

    def fileno(self):
        assert self.sessp
        transport = lib.snmp_sess_transport(self.sessp)
        return transport.contents.sock

    def timeout(self):
        assert self.sessp
        fd_max = ctypes.c_int()
        fd_set = _mkfdset(self.fileno())
        tv = types.timeval()
        block = ctypes.c_int(1) # block = 1 means tv is undefined

        # We only actually need tv and block
        lib.snmp_sess_select_info(self.sessp,
                byref(fd_max), byref(fd_set),
                byref(tv), byref(block))

        if block:
            return None
        else:
            return tv.tv_sec + tv.tv_usec / 1000000.0

    def _callback(self, operation, sp, reqid, pdu, magic):
        try:
            if reqid not in self._requests:
                return 1

            cb, args = self._requests.pop(reqid)

            if operation == const.NETSNMP_CALLBACK_OP_RECEIVED_MESSAGE:
                result = util.decode_result(pdu.contents)
                cb(result, *args)
            elif operation == const.NETSNMP_CALLBACK_OP_TIMED_OUT:
                cb(SnmpTimeout(), *args)
            else:
                raise Exception("Unexpected operation: %d" % operation)
        except Exception, ex:
            # This shouldn't happen, but just in case...
            # TODO: Probably should use the logging api instead.
            sys.stderr.write("Exception in _callback: %s\n" % (ex,))
        return 1

    def _create_request(self, msg_type, oids):
        req = lib.snmp_pdu_create(msg_type)
        for oid in oids:
            oid = util.encode_oid(oid)
            lib.snmp_add_null_var(req, oid, len(oid))
        return req

    def _send_request(self, msg_type, oids, cb, *args):
        assert self.sessp
        req = self._create_request(msg_type, oids)
        self._requests[req.contents.reqid] = (cb, args)

        if not lib.snmp_sess_send(self.sessp, req):
            lib.snmp_free_pdu(req)
            del self._requests[req.contents.reqid]
            raise SnmpError("snmp_sess_send")

    def sget(self, oids):
        assert self.sessp
        req = self._create_request(const.SNMP_MSG_GET, oids)
        response = types.netsnmp_pdu_p()

        if lib.snmp_sess_synch_response(self.sessp, req, byref(response)):
            raise SnmpError("snmp_sess_synch_response")

        result = util.decode_result(response.contents)
        lib.snmp_free_pdu(response)
        return result

    def get(self, oids, cb, *args):
        self._send_request(const.SNMP_MSG_GET, oids, cb, *args)

    def getnext(self, oids, cb, *args):
        self._send_request(const.SNMP_MSG_GETNEXT, oids, cb, *args)

    def walk(self, oids, cb, *args):
        """Walk using a sequence of getnext requests"""

        oids = [util.parse_oid(x) for x in oids]
        tree = {}

        # This is a little simple minded and simply stops the walk
        # when we evaluate a result to None but None could result
        # due to situations other than the end of the tree.
        # TODO: check for the true end of the tree instead.
        # Note: v1 and v2c report this condition in different ways.
        def walk_cb(value, root):
            if isinstance(value, Exception):
                cb(value, *args)
                return

            oid = value.keys()[0]
            if value[oid] is None or not oid.startswith(root):
                start_or_stop()
            else:
                tree.update(value)
                self._send_request(const.SNMP_MSG_GETNEXT,
                        [oid], walk_cb, root)

        def first_cb(value):
            if isinstance(value, Exception):
                cb(value, *args)
                return

            oid = value.keys()[0]
            if value[oid] is not None:
                tree.update(value)
                start_or_stop()
            else:
                self._send_request(const.SNMP_MSG_GETNEXT,
                        [oid], walk_cb, oid)

        def start_or_stop():
            if oids:
                oid = oids.pop()
                self._send_request(const.SNMP_MSG_GET, [oid], first_cb)
            else:
                cb(tree, *args)

        start_or_stop()

    def do_timeout(self):
        assert self.sessp
        lib.snmp_sess_timeout(self.sessp)

    def do_read(self):
        assert self.sessp
        fd_set = _mkfdset(self.fileno())
        lib.snmp_sess_read(self.sessp, byref(fd_set))

    def wait(self):
        """Wait for any outstanding requests/timeouts"""

        while self._requests:
            timeout = self.timeout()

            read, w, x = select.select((self.fileno(),), (), (), timeout)

            if read:
                self.do_read()
            else:
                self.do_timeout()


#    def getbulk(self, nonrepeaters, maxrepetitions, oids):
#        assert self.sessp
#        req = self._create_request(SNMP_MSG_GETBULK)
#        req = cast(req, POINTER(netsnmp_pdu))
#        req.contents.errstat = nonrepeaters
#        req.contents.errindex = maxrepetitions
#        for oid in oids:
#            oid = mkoid(oid)
#            lib.snmp_add_null_var(req, oid, len(oid))
#        if not lib.snmp_sess_send(self.sessp, req):
#            lib.snmp_free_pdu(req)
#            raise SnmpError("snmp_send")
#        return req.contents.reqid

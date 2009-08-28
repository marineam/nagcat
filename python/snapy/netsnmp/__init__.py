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

# Provide easier access to types the user will see
ExceptionValue = types.ExceptionValue
NoSuchObject = types.NoSuchObject
NoSuchInstance = types.NoSuchInstance
EndOfMibView = types.EndOfMibView

# The normal fd limit
FD_SETSIZE = 1024

def _mkfdset(fd):
    """Make a fd set of the right size and set fd"""
    size = max(fd+1, FD_SETSIZE)
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

        # We must hold a reference to argv so it isn't deleted
        self._session_argv = _parse_args(args, self.session_template)

    def error(self):
        pass

    def open(self):
        sess = types.netsnmp_session()
        ctypes.memmove(byref(sess),
                byref(self.session_template), ctypes.sizeof(sess))

        # We must hold a reference to the callback while it is in use
        self._session_callback = types.netsnmp_callback(self._callback)
        sess.callback = self._session_callback

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
        self._session_callback = None

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
            raise

        return 1

    def _create_request(self, msg_type, oids, **pdu_args):
        req = lib.snmp_pdu_create(msg_type)

        for opt, val in pdu_args.iteritems():
            setattr(req.contents, opt, val)

        for oid in oids:
            oid = util.encode_oid(oid)
            lib.snmp_add_null_var(req, oid, len(oid))

        return req

    def _send_request(self, msg_type, oids, cb, *args, **pdu_args):
        """Create and send the pdu for the given type and oids.

        @param msg_type: one of const.SNMP_MSG_*
        @param oids: sequence of oids to request
        @param cb: callback function, result is the first argument
        @param args: extra callback arguments
        @param pdu_args: extra attributes to set in the request pdu
        """

        assert self.sessp
        req = self._create_request(msg_type, oids, **pdu_args)
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

    def getbulk(self, oids, non_repeaters, max_repetitions, cb, *args):
        self._send_request(const.SNMP_MSG_GETBULK, oids, cb, *args,
                errstat=non_repeaters, errindex=max_repetitions)

    def walk(self, oids, cb, *args):
        """Walk using GETBULK or GETNEXT"""

        if not oids:
            return {}

        # Parse and sort the oids, they must be in order
        # so we know how far though the walk we have gotten.
        oids = list(set(util.parse_oid(x) for x in oids))
        oids.sort(cmp=util.compare_oids)

        # Status on the tree needs to be shared between the
        # callbacks, wrap up in a dict to avoid scoping issues
        tree = {}

        # The base oid of the current tree we are processing
        tree['base'] = None

        # The last oid we saw in the current tree
        tree['last'] = None

        # The final value(s)
        data = []

        def walk_cb(results):
            if isinstance(results, Exception):
                stop(results)
                return

            # We must process things in order
            results.sort(cmp=util.compare_results)

            for oid, value in results:
                # Stop when an error is hit (ie endOfMibView)
                if isinstance(value, ExceptionValue):
                    stop()
                    return

                # Stop if the server's snmp server sucks and goes backwards
                if oids and util.compare_oids(oid, tree['base']) <= 0:
                    stop()
                    return

                # Remove OIDs that have been passed
                while oids and util.compare_oids(oid, oids[0]) > 0:
                    old = oids.pop(0)
                    # Are we in a new tree?
                    if not old.startswith(tree['base']):
                        tree['base'] = old

                # Make sure we are still in the requested tree
                if not oid.startswith(tree['base']):
                    tree['last'] = None
                    continue

                # Great! We got a value! save it and mark our position
                data.append((oid, value))
                tree['last'] = oid

            # If we have a large tree we need to continue fetching
            # insert our stopping point.
            if tree['last']:
                oids.insert(0, tree['last'])

            next()

        def get_cb(results):
            if isinstance(results, Exception):
                stop(results)
                return

            # Save any valid results, the remaining will be walked
            for oid, value in results:
                if not isinstance(value, ExceptionValue):
                    data.append((oid, value))
                    oids.remove(oid)

            if oids:
                tree['base'] = oids[0]
            next()

        def next():
            if oids:
                if self.session.contents.version == const.SNMP_VERSION_1:
                    oid = oids.pop(0)
                    self._send_request(const.SNMP_MSG_GETNEXT, [oid], walk_cb)
                else:
                    # Fetch 50 results at a time, is this a good value?
                    # Note: errstat=non_repeaters, errindex=max_repetitions
                    self._send_request(const.SNMP_MSG_GETBULK, oids,
                            walk_cb, errstat=0, errindex=50)
            else:
                stop()

        def stop(results=None):
            if results is None:
                data.sort(cmp=util.compare_results)
                results = data
            cb(results, *args)

        self._send_request(const.SNMP_MSG_GET, oids, get_cb)

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

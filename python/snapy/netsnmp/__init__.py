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
import select
import ctypes
from ctypes import byref

lib = ctypes.CDLL("libnetsnmp.so", ctypes.RTLD_GLOBAL)

from snapy.netsnmp import const, types, util

"""Net-SNMP bindings for the single session API"""

class SnmpError(Exception):
    """Generic SNMP Error"""
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
OID = types.OID

class Session(object):
    """Wrapper around a single SNMP Session"""

    def __init__(self, **kwargs):
        """The keywords set various options in struct snmp_session.

        At the minimum you will want the following kwargs:
        @param version: "1" or "2c" (haven't tested 3 yet)
        @param peername: host and possibly transport and port
            for example: "host" or "udp:host:port"
        @param community: v1/2 community, ie: "public"

        Other useful things include:
        @param retries: number of retries before giving up
        @param timeout: seconds time between retries
        """

        self.sessp = None   # single session api pointer
        self.session = None # session struct
        self.session_template = types.netsnmp_session()
        self._requests = {}

        # Initialize session to default values
        lib.snmp_sess_init(byref(self.session_template))

        # Convert from a string to the numeric constant
        if 'version' not in kwargs:
            raise SnmpError("Keyword version is required")
        elif kwargs['version'] == '1':
            kwargs['version'] = const.SNMP_VERSION_1
        elif kwargs['version'] == '2c':
            kwargs['version'] = const.SNMP_VERSION_2c
        else:
            raise SnmpError("Invalid version: %r" % kwargs['version'])

        if 'peername' not in kwargs:
            raise SnmpError("Keyword peername is required")
        elif not isinstance(kwargs['peername'], str):
            raise SnmpError("Invalid peername, must be a str")

        # Check community is a str, set community_len
        if 'community' not in kwargs:
            raise SnmpError("Keyword community is required")
        elif not isinstance(kwargs['community'], str):
            raise SnmpError("Invalid community, must be a str")
        else:
            kwargs['community_len'] = len(kwargs['community'])

        # Convert from seconds to microseconds
        if 'timeout' in kwargs:
            kwargs['timeout'] = int(kwargs['timeout'] * 1e6)

        for attr, value in kwargs.iteritems():
            setattr(self.session_template, attr, value)

        # We must hold a reference to the callback while it is in use
        self._session_callback = types.netsnmp_callback(self._callback)
        self.session_template.callback = self._session_callback

    def open(self):
        #sess = types.netsnmp_session()
        #ctypes.memmove(byref(sess),
        #        byref(self.session_template), ctypes.sizeof(sess))

        # We must hold a reference to the callback while it is in use
        #self._session_callback = types.netsnmp_callback(self._callback)
        #sess.callback = self._session_callback

        self.sessp = lib.snmp_sess_open(byref(self.session_template))
        if not self.sessp:
            raise SnmpError('snmp_sess_open')

        self.session = lib.snmp_sess_session(self.sessp)

    def close(self):
        assert self.sessp
        lib.snmp_sess_close(self.sessp)
        self.sessp = None
        self.session = None
        self._session_callback = None
        self._requests.clear()

    def fileno(self):
        assert self.sessp
        transport = lib.snmp_sess_transport(self.sessp)
        return transport.contents.sock

    def timeout(self):
        assert self.sessp
        tv = types.timeval()
        block = ctypes.c_int(1) # block = 1 means tv is undefined

        # Note that we have to use a different select_info call
        # depending on the netsnmp version, also out of the info
        # it returns we only actually need tv and block. So all
        # this crap just to handle large fds is pointless. Win.
        self._timeout_compat(tv, block)

        if block:
            return None
        else:
            return tv.tv_sec + tv.tv_usec / 1000000.0

    if types.lib_version_info >= (5,5):
        def _timeout_compat(self, tv, block):
            fd_max = ctypes.c_int()
            fd_set = types.mkfdset2(self.fileno())
            lib.snmp_sess_select_info2(self.sessp,
                    byref(fd_max), byref(fd_set),
                    byref(tv), byref(block))
            types.rmfdset2(fd_set)
    else:
        def _timeout_compat(self, tv, block):
            fd_max = ctypes.c_int()
            fd_set = types.mkfdset(self.fileno())
            lib.snmp_sess_select_info(self.sessp,
                    byref(fd_max), fd_set,
                    byref(tv), byref(block))

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
            oid = OID(oid)
            lib.snmp_add_null_var(req, oid.raw, len(oid))

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

    def _uniq(self, oids):
        return list(set(OID(x) for x in oids))

    def sget(self, oids):
        assert self.sessp
        req = self._create_request(const.SNMP_MSG_GET, oids)
        response = ctypes.POINTER(types.netsnmp_pdu)()

        if lib.snmp_sess_synch_response(self.sessp, req, byref(response)):
            raise SnmpError("snmp_sess_synch_response")

        result = util.decode_result(response.contents)
        lib.snmp_free_pdu(response)
        return result

    def get(self, oids, cb, *args):
        oids = self._uniq(oids)
        data = []

        def walk_cb(results):
            if isinstance(results, Exception):
                cb(results, *args)
                return

            for oid, value in results:
                try:
                    oids.remove(oid)
                except:
                    # Unexpected value! Abort!
                    cb(data, *args)
                    return

                if not isinstance(value, ExceptionValue):
                    data.append((oid, value))

            if oids:
                self._send_request(const.SNMP_MSG_GET, oids[:10], walk_cb)
            else:
                data.sort(cmp=util.compare_results)
                cb(data, *args)

        self._send_request(const.SNMP_MSG_GET, oids[:10], walk_cb)

    def walk(self, oids, cb, *args, **kwargs):
        """Walk using GETBULK or GETNEXT

        The only keyword argument supported is 'strict'.
        (I'd rather say *args, strict=False but that is invalid)

        If strict is False then a GET will be attempted as well.
        """

        if not oids:
            return {}

        # Parse and sort the oids, they must be in order
        # so we know how far though the walk we have gotten.
        oids = self._uniq(oids)
        oids.sort()

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
                if oid <= tree['base']:
                    stop()
                    return

                # Remove OIDs that have been passed
                while oids and oid > oids[0]:
                    tree['base'] = oids.pop(0)

                # Make sure we are still in the requested tree
                if not oid.startswith(tree['base']):
                    tree['last'] = None
                else:
                    tree['last'] = oid
                    data.append((oid, value))

            next()

        def get_cb(results):
            if isinstance(results, Exception):
                stop(results)
                return

            # Save any results, the remaining will be walked
            for oid, value in results:
                data.append((oid, value))
                oids.remove(oid)

            next()

        def next():
            if tree['last']:
                oid = tree['last']
            elif oids:
                oid = oids.pop(0)
                tree['base'] = oid
            else:
                stop()
                return

            if self.session.contents.version == const.SNMP_VERSION_1:
                self._send_request(const.SNMP_MSG_GETNEXT, [oid], walk_cb)
            else:
                # Fetch 50 results at a time, is this a good value?
                # Note: errstat=non_repeaters, errindex=max_repetitions
                self._send_request(const.SNMP_MSG_GETBULK, [oid],
                        walk_cb, errstat=0, errindex=10)

        def stop(results=None):
            if results is None:
                data.sort(cmp=util.compare_results)
                results = data
            cb(results, *args)

        if kwargs.get('strict', False):
            next()
        else:
            self.get(oids, get_cb)

    def do_timeout(self):
        assert self.sessp
        lib.snmp_sess_timeout(self.sessp)

    def do_read(self):
        assert self.sessp
        self._read_compat()

    if types.lib_version_info >= (5,5):
        def _read_compat(self):
            fd_set = types.mkfdset2(self.fileno())
            lib.snmp_sess_read2(self.sessp, byref(fd_set))
            types.rmfdset2(fd_set)
    else:
        def _read_compat(self):
            fd_set = types.mkfdset(self.fileno())
            lib.snmp_sess_read(self.sessp, fd_set)

    def wait(self):
        """Wait for any outstanding requests/timeouts"""

        while self._requests:
            timeout = self.timeout()

            read, w, x = select.select((self.fileno(),), (), (), timeout)

            if read:
                self.do_read()
            else:
                self.do_timeout()

import ctypes
from ctypes import byref
from ctypes.util import find_library

lib = ctypes.CDLL(find_library('netsnmp'), ctypes.RTLD_GLOBAL)

from snapy.netsnmp import const, types, util

class SnmpError(Exception):
    """Error in NetSNMP"""
    pass

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
        self.session_argv = _parse_args(args, self.session_template)

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

    def close(self):
        assert self.sessp

        lib.snmp_sess_close(self.sessp)
        #del sessionMap[id(self)]
        self.sessp = None
        self.session = None

    def callback(self, pdu):
        pass

    def timeout(self, reqid):
        pass

    def _create_request(self, msg_type, oids):
        req = lib.snmp_pdu_create(msg_type)
        for oid in oids:
            oid = util.encode_oid(oid)
            lib.snmp_add_null_var(req, oid, len(oid))
        return req

    def sget(self, oids):
        assert self.sessp
        req = self._create_request(const.SNMP_MSG_GET, oids)
        response = types.netsnmp_pdu_p()
        if lib.snmp_sess_synch_response(self.sessp, req, byref(response)) == 0:
            result = util.decode_result(response.contents)
            lib.snmp_free_pdu(response)
            return result

#    def get(self, oids):
#        assert self.sessp
#        req = self._create_request(SNMP_MSG_GET, oids)
#        if not lib.snmp_sess_send(self.sessp, req):
#            lib.snmp_free_pdu(req)
#            raise SnmpError("snmp_send")
#        return req.contents.reqid
#
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
#
#    def walk(self, root):
#        assert self.sessp
#        req = self._create_request(SNMP_MSG_GETNEXT)
#        oid = mkoid(root)
#        lib.snmp_add_null_var(req, oid, len(oid))
#        if not lib.snmp_sess_send(self.sess, req):
#            lib.snmp_free_pdu(req)
#            raise SnmpError("snmp_send")
#        return req.contents.reqid

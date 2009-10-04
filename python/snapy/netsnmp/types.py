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

from __future__ import division

import math
from ctypes import *
from snapy.netsnmp import const, lib

# Provide the standard timeval struct
class timeval(Structure):
    _fields_ = [
        ('tv_sec', c_long),
        ('tv_usec', c_long),
        ]

# The normal fd_set types and sizes
fd_mask = c_ulong
fd_set_p = POINTER(fd_mask)

FD_SETSIZE = 1024
NFDBITS = 8 * sizeof(fd_mask)

fd_set = fd_mask * (FD_SETSIZE // NFDBITS)

# Magical generator for a fd_set, used for netsnmp < 5.5
def mkfdset(fd):
    """Make a fd set of the right size and set fd"""

    size = max(fd+1, FD_SETSIZE)
    sized_fd_set_t = fd_mask * int(math.ceil(size / NFDBITS))
    sized_fd_set = sized_fd_set_t()
    sized_fd_set[fd // NFDBITS] |= 1 << (fd % NFDBITS)
    return cast(sized_fd_set, fd_set_p)


# Match netsnmp's data types (mostly)
oid = c_long
u_char_p = c_char_p
u_char = c_ubyte
c_int_p = POINTER(c_int)

class netsnmp_session(Structure): pass
class netsnmp_transport(Structure): pass
class netsnmp_pdu(Structure): pass
class netsnmp_variable_list(Structure): pass

## Set library arg and return types ##

# net-snmp/version.h
lib.netsnmp_get_version.argtypes = []
lib.netsnmp_get_version.restype = c_char_p

lib_version = lib.netsnmp_get_version()
lib_version_info = tuple(int(x) for x in lib_version.split('.'))
if lib_version_info < (5,1):
    raise ImportError("netsnmp version 5.1 or greater is required")

# net-snmp/pdu_api.h
lib.snmp_pdu_create.argtypes = [c_int]
lib.snmp_pdu_create.restype = POINTER(netsnmp_pdu)
lib.snmp_free_pdu.argtypes = [POINTER(netsnmp_pdu)]
lib.snmp_free_pdu.restype = None

# net-snmp/varbind_api.h
lib.snmp_add_null_var.argtypes = [POINTER(netsnmp_pdu), POINTER(oid), c_size_t]
lib.snmp_add_null_var.restype = POINTER(netsnmp_variable_list)

# net-snmp/session_api.h
lib.snmp_sess_open.argtypes = [POINTER(netsnmp_session)]
lib.snmp_sess_open.restype = c_void_p
lib.snmp_sess_close.argtypes = [c_void_p]
lib.snmp_sess_close.restype = c_int
lib.snmp_sess_session.argtypes = [c_void_p]
lib.snmp_sess_session.restype = POINTER(netsnmp_session)
lib.snmp_sess_transport.argtypes = [c_void_p]
lib.snmp_sess_transport.restype = POINTER(netsnmp_transport)
lib.snmp_sess_select_info.argtypes = [c_void_p, c_int_p, fd_set_p,
                                      POINTER(timeval), c_int_p]
lib.snmp_sess_select_info.restype = c_int
lib.snmp_sess_timeout.argtypes = [c_void_p]
lib.snmp_sess_timeout.restype = None
lib.snmp_sess_send.argtypes = [c_void_p, POINTER(netsnmp_pdu)]
lib.snmp_sess_send.restype = c_int
lib.snmp_sess_read.argtypes = [c_void_p, fd_set_p]
lib.snmp_sess_read.restype = c_int

if lib_version_info >= (5,5):
    # >= 5.5 requires the use of a special fd set type for >= 1024
    class netsnmp_large_fd_set(Structure):
        _fields_ = [
                ('lfs_setsize', c_uint),
                ('lfs_setptr', POINTER(fd_set)),
                ('lfs_set', fd_set),
        ]

    def mkfdset2(fd):
        fd_set = netsnmp_large_fd_set()
        lib.netsnmp_large_fd_set_init(byref(fd_set), fd+1)
        lib.netsnmp_large_fd_setfd(fd, byref(fd_set))
        return fd_set

    def rmfdset2(fd_set):
        lib.netsnmp_large_fd_set_cleanup(byref(fd_set))

    # net-snmp/library/large_fd_set.h
    lib.netsnmp_large_fd_set_init.argtypes = [POINTER(netsnmp_large_fd_set), c_int]
    lib.netsnmp_large_fd_set_init.restype = None
    lib.netsnmp_large_fd_setfd.argtypes = [c_int, POINTER(netsnmp_large_fd_set)]
    lib.netsnmp_large_fd_setfd.restype = None
    lib.netsnmp_large_fd_set_cleanup.argtypes = [POINTER(netsnmp_large_fd_set)]
    lib.netsnmp_large_fd_set_cleanup.restype = None

    # net-snmp/session_api.h
    lib.snmp_sess_select_info2.argtypes = [c_void_p, c_int_p,
                                           POINTER(netsnmp_large_fd_set),
                                           POINTER(timeval), c_int_p]
    lib.snmp_sess_select_info2.restype = c_int
    lib.snmp_sess_read2.argtypes = [c_void_p, POINTER(netsnmp_large_fd_set)]
    lib.snmp_sess_read2.restype = c_int


authenticator = CFUNCTYPE(c_char_p, c_int_p, c_char_p, c_int)

# Event callback
# int (*netsnmp_callback) (int, netsnmp_session *, int, netsnmp_pdu *, void *);
netsnmp_callback = CFUNCTYPE(c_int,
                             c_int, POINTER(netsnmp_session),
                             c_int, POINTER(netsnmp_pdu),
                             c_void_p)

localname = []
paramName = []
if lib_version_info >= (5,2):
    localname = [('localname', c_char_p)]
if lib_version_info >= (5,3):
    paramName = [('paramName', c_char_p)]

netsnmp_session._fields_ = [
        ('version', c_long),
        ('retries', c_int),
        ('timeout', c_long),
        ('flags', c_ulong),
        ('subsession', POINTER(netsnmp_session)),
        ('next', POINTER(netsnmp_session)),
        ('peername', c_char_p),
        ('remote_port', c_ushort),
        ] + localname + [
        ('local_port', c_ushort),
        ('authenticator', authenticator),
        ('callback', netsnmp_callback),
        ('callback_magic', c_void_p),
        ('s_errno', c_int),
        ('s_snmp_errno', c_int),
        ('sessid', c_long),
        ('community', u_char_p),
        ('community_len', c_size_t),
        ('rcvMsgMaxSize', c_size_t),
        ('sndMsgMaxSize', c_size_t),

        ('isAuthoritative', u_char),
        ('contextEngineID', u_char_p),
        ('contextEngineIDLen', c_size_t),
        ('engineBoots', c_uint),
        ('engineTime', c_uint),
        ('contextName', c_char_p),
        ('contextNameLen', c_size_t),
        ('securityEngineID', u_char_p),
        ('securityEngineIDLen', c_size_t),
        ('securityName', c_char_p),
        ('securityNameLen', c_size_t),

        ('securityAuthProto', POINTER(oid)),
        ('securityAuthProtoLen', c_size_t),
        ('securityAuthKey', u_char * const.USM_AUTH_KU_LEN),
        ('securityAuthKeyLen', c_size_t),
        ('securityAuthLocalKey', c_char_p),
        ('securityAuthLocalKeyLen', c_size_t),

        ('securityPrivProto', POINTER(oid)),
        ('securityPrivProtoLen', c_size_t),
        ('securityPrivKey', c_char * const.USM_PRIV_KU_LEN),
        ('securityPrivKeyLen', c_size_t),
        ('securityPrivLocalKey', c_char_p),
        ('securityPrivLocalKeyLen', c_size_t),

        ] + paramName + [

        ('securityModel', c_int),
        ('securityLevel', c_int),

        ('securityInfo', c_void_p),

        ('myvoid', c_void_p),
        ]

class counter64(Structure):
    _fields_ = [
        ('high', c_ulong),
        ('low', c_ulong),
        ]

class netsnmp_vardata(Union):
    _fields_ = [
        ('integer', POINTER(c_long)),
        ('uinteger', POINTER(c_ulong)),
        ('string', c_char_p),
        ('objid', POINTER(oid)),
        ('bitstring', POINTER(c_ubyte)),
        ('counter64', POINTER(counter64)),
        ('floatVal', POINTER(c_float)),
        ('doubleVal', POINTER(c_double)),
        ]

dataFreeHook = CFUNCTYPE(c_void_p)

netsnmp_variable_list._fields_ = [
        ('next_variable', POINTER(netsnmp_variable_list)),
        ('name', POINTER(oid)),
        ('name_length', c_size_t),
        ('type', u_char),
        ('val', netsnmp_vardata),
        ('val_len', c_size_t),
        ('name_loc', oid * const.MAX_OID_LEN),
        ('buf', c_char * 40),
        ('data', c_void_p),
        ('dataFreeHook', dataFreeHook),
        ('index', c_int),
        ]

netsnmp_pdu._fields_ = [
        ('version', c_long ),
        ('command', c_int ),
        ('reqid', c_long ),
        ('msgid', c_long ),
        ('transid', c_long ),
        ('sessid', c_long ),
        ('errstat', c_long ),   # (non_repeaters in GetBulk)
        ('errindex', c_long ),  # (max_repetitions in GetBulk)
        ('time', c_ulong ),
        ('flags', c_ulong ),
        ('securityModel', c_int ),
        ('securityLevel', c_int ),
        ('msgParseModel', c_int ),
        ('transport_data', c_void_p),
        ('transport_data_length', c_int ),
        ('tDomain', POINTER(oid)),
        ('tDomainLen', c_size_t ),
        ('variables', POINTER(netsnmp_variable_list)),
        ('community', c_char_p),
        ('community_len', c_size_t ),
        ('enterprise', POINTER(oid)),
        ('enterprise_length', c_size_t ),
        ('trap_type', c_long ),
        ('specific_type', c_long ),
        ('agent_addr', c_ubyte * 4),
        ('contextEngineID', c_char_p ),
        ('contextEngineIDLen', c_size_t ),
        ('contextName', c_char_p),
        ('contextNameLen', c_size_t ),
        ('securityEngineID', c_char_p),
        ('securityEngineIDLen', c_size_t ),
        ('securityName', c_char_p),
        ('securityNameLen', c_size_t ),
        ('priority', c_int ),
        ('range_subid', c_int ),
        ('securityStateRef', c_void_p),
        ]

tmStateRef = []
if lib_version_info >= (5,5):
    tmStateRef = [('tmStateRef', c_void_p)]

netsnmp_transport._fields_ = [
        ('domain', POINTER(oid)),
        ('domain_length', c_int),
        ('local', u_char_p),
        ('local_length', c_int),
        ('remote', u_char_p),
        ('remote_length', c_int),
        ('sock', c_int),
        ('flags', c_uint),
        ('data', c_void_p),
        ('data_length', c_int),
        ('msgMaxSize', c_size_t),
        ] + tmStateRef + [
        ('f_recv', c_void_p),
        ('f_send', c_void_p),
        ('f_close', c_void_p),
        ('f_accept',  c_void_p),
        ('f_fmtaddr', c_void_p),
]


# Special error types that are returned as values
class ExceptionValue(object):
    """Parent class of all special snmp error values"""

    def __str__(self):
        return self.__class__.__doc__

class NoSuchObject(ExceptionValue):
    """No Such Object"""

class NoSuchInstance(ExceptionValue):
    """No Such Instance"""

class EndOfMibView(ExceptionValue):
    """End of MIB View"""

class PacketError(ExceptionValue):
    """Packet Error"""

    def __init__(self, code):
        self.code = code

    def __str__(self):
        return "%s: %s" % (self.__class__.__doc__, self.code)

class OID(tuple):
    """An OID and various helper methods.

    The OID.raw attribute can be used for library calls.

    >>> oid = OID("1.2.3.4")
    >>> lib.snmp_add_null_var(req, oid.raw, len(oid))
    """

    def __new__(cls, seq, length=None):
        """Note: length should only be used for sequence types that
        may not be able to report their length properly."""
        if isinstance(seq, OID):
            return seq
        elif isinstance(seq, basestring):
            # TODO: Handle strings like: SNMPv2-MIB::sysDescr.0
            seq = [int(v) for v in seq.strip('.').split('.')]
        elif length:
            seq = [int(seq[i]) for i in xrange(length)]
        else:
            # Just to make sure everyitng is an int
            seq = [int(v) for v in seq]

        self = super(OID, cls).__new__(cls, seq)
        self.raw = (oid * len(self))()
        for i, v in enumerate(self):
            self.raw[i] = v

        return self

    def __str__(self):
        return ".%s" % ".".join(str(i) for i in self)

    def __repr__(self):
        return "OID(%r)" % list(self)

    def __add__(self, other):
        return OID(super(OID, self).__add__(other))

    def startswith(self, other):
        """String like startswith method for comparing OIDs"""

        if not isinstance(other, OID):
            other = OID(other)
        return self[:len(other)] == other

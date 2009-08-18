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

import ctypes

from snapy.netsnmp import const, types

def _parse_oid(oid):
    # TODO: Handle strings like: SNMPv2-MIB::sysDescr.0
    if isinstance(oid, str):
        oid = [int(v) for v in oid.strip('.').split('.')]
    return oid

def parse_oid(oid):
    oid = _parse_oid(oid)
    return decode_oid(oid, len(oid))

def encode_oid(oid):
    oid = _parse_oid(oid)
    raw = (types.oid * len(oid))()
    for i, v in enumerate(oid):
        raw[i] = v
    return raw

def decode_oid(raw, length):
    return "."+".".join([str(raw[i]) for i in xrange(length)])

def _decode_objid(var):
    length = var.val_len / ctypes.sizeof(types.oid)
    return decode_oid(var.val.objid, length)

def _decode_ip(var):
    return '.'.join(map(str, var.val.bitstring[:4]))

def _decode_counter64(var):
    int64 = var.val.counter64.contents
    return (int64.high << 32L) + int64.low

def _decode_string(var):
    if var.val_len:
        return ctypes.string_at(var.val.bitstring, var.val_len)
    return ''

_decoder = {
    const.ASN_OCTET_STR:    _decode_string,
    const.ASN_BOOLEAN:      lambda var: var.val.integer.contents.value,
    const.ASN_INTEGER:      lambda var: var.val.integer.contents.value,
    const.ASN_NULL:         lambda var: None,
    const.ASN_OBJECT_ID:    _decode_objid,
    const.ASN_BIT_STR:      _decode_string,
    const.ASN_IPADDRESS:    _decode_ip,
    const.ASN_COUNTER:      lambda var: var.val.uinteger.contents.value,
    const.ASN_GAUGE:        lambda var: var.val.uinteger.contents.value,
    const.ASN_TIMETICKS:    lambda var: var.val.uinteger.contents.value,
    const.ASN_COUNTER64:    _decode_counter64,
    const.ASN_APP_FLOAT:    lambda var: var.val.float.contents.value,
    const.ASN_APP_DOUBLE:   lambda var: var.val.double.contents.value,
    }

def _decode_variable(var):
    oid = decode_oid(var.name, var.name_length)
    decode = _decoder.get(var.type, None)
    if not decode:
        return (oid, None)
    return oid, decode(var)

def decode_result(pdu):
    result = {}
    var = pdu.variables
    while var:
        var = var.contents
        oid, value = _decode_variable(var)
        result[oid] = value
        var = var.next_variable
    return result

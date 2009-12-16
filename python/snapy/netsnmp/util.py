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

from snapy.netsnmp import lib, const, types

def _decode_objid(objid, var):
    length = var.val_len / ctypes.sizeof(types.oid)
    return types.OID(var.val.objid, length)

def _decode_ip(objid, var):
    return '.'.join(map(str, var.val.bitstring[:4]))

def _decode_counter64(objid, var):
    int64 = var.val.counter64.contents
    return (int64.high << 32L) + int64.low

def _decode_raw_string(objid, var):
    return ctypes.string_at(var.val.bitstring, var.val_len)

def _decode_string(objid, var):
    """Decode a string value, we make use of the mib aware
    snmprint_value to make the string still useful for "special"
    values such as HOST-RESOURCES-MIB::hrSystemDate.0
    """
    hint = objid.hint()
    if hint:
        buf_len = 256 # 256 is what net-snmp tends to use
        buf = ctypes.create_string_buffer(buf_len)
        lib.snprint_octet_string(buf, buf_len,
                ctypes.byref(var), None, hint, None)
        return str(buf.value)
    else:
        return _decode_raw_string(objid, var)

# TODO: Add support for converting integers to enum strings,
# OID.enums() should provide this mapping but is untested.

_decoder = {
    const.ASN_OCTET_STR:    _decode_string,
    const.ASN_BOOLEAN:      lambda id, var: var.val.integer.contents.value,
    const.ASN_INTEGER:      lambda id, var: var.val.integer.contents.value,
    const.ASN_NULL:         lambda id, var: None,
    const.ASN_OBJECT_ID:    _decode_objid,
    const.ASN_BIT_STR:      _decode_raw_string,
    const.ASN_IPADDRESS:    _decode_ip,
    const.ASN_COUNTER:      lambda id, var: var.val.uinteger.contents.value,
    const.ASN_GAUGE:        lambda id, var: var.val.uinteger.contents.value,
    const.ASN_TIMETICKS:    lambda id, var: var.val.uinteger.contents.value,
    const.ASN_COUNTER64:    _decode_counter64,
    const.ASN_APP_FLOAT:    lambda id, var: var.val.float.contents.value,
    const.ASN_APP_DOUBLE:   lambda id, var: var.val.double.contents.value,

    # Errors
    const.SNMP_NOSUCHOBJECT:    lambda id, var: types.NoSuchObject(),
    const.SNMP_NOSUCHINSTANCE:  lambda id, var: types.NoSuchInstance(),
    const.SNMP_ENDOFMIBVIEW:    lambda id, var: types.EndOfMibView(),
    }

def _decode_variable(objid, var):
    if var.type not in _decoder:
        raise Exception("SNMP data type %d not implemented" % var.type)
    return _decoder[var.type](objid, var)

def _decode_error(error):
    if error == const.SNMP_ERR_NOSUCHNAME:
        value = types.NoSuchObject()
    else:
        value = types.PacketError(error)
    return value

def decode_result(pdu):
    result = []

    # Check for an error
    err_index = None
    if pdu.errstat != const.SNMP_ERR_NOERROR:
        err_index = pdu.errindex

    var = pdu.variables
    index = 1
    while var:
        var = var.contents
        oid = types.OID(var.name, var.name_length)

        if err_index is None:
            result.append((oid, _decode_variable(oid, var)))
        elif err_index == index:
            result.append((oid, _decode_error(pdu.errstat)))
            break

        var = var.next_variable
        index += 1

    if not result and err_index is not None:
        return [(types.OID(), _decode_error(pdu.errstat))]
    else:
        return result

def compare_results(result1, result2):
    """Useful for sorting the list returned by decode_result"""
    return cmp(result1[0], result2[0])

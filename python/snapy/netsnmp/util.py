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

def _decode_objid(var):
    length = var.val_len / ctypes.sizeof(types.oid)
    return types.OID(var.val.objid, length)

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

    # Errors
    const.SNMP_NOSUCHOBJECT:    lambda var: types.NoSuchObject(),
    const.SNMP_NOSUCHINSTANCE:  lambda var: types.NoSuchInstance(),
    const.SNMP_ENDOFMIBVIEW:    lambda var: types.EndOfMibView(),
    }

def _decode_variable(var):
    if var.type not in _decoder:
        raise Exception("SNMP data type %d not implemented" % var.type)
    oid = types.OID(var.name, var.name_length)
    return oid, _decoder[var.type](var)

def _decode_varerror(var, error):
    oid = types.OID(var.name, var.name_length)

    if error == const.SNMP_ERR_NOSUCHNAME:
        value = types.NoSuchObject()
    else:
        # TODO: do a better job here...
        value = Exception("got error code: %d" % error)

    return (oid, value)

def decode_result(pdu):
    result = []

    # Check for an error
    last_index = None
    if pdu.errstat != const.SNMP_ERR_NOERROR:
        last_index = pdu.errindex

    var = pdu.variables
    index = 1
    while var:
        if last_index is not None and index >= last_index:
            result.append(_decode_varerror(var.contents, pdu.errstat))
            break
        else:
            result.append(_decode_variable(var.contents))
            var = var.contents.next_variable
            index += 1

    return result

def compare_results(result1, result2):
    """Useful for sorting the list returned by decode_result"""
    return cmp(result1[0], result2[0])

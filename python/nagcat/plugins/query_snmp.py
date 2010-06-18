# Copyright 2008-2010 ITA Software, Inc.
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

"""SNMP Querys"""

from zope.interface import classProvides
from twisted.internet import error as neterror
from twisted.python import failure

from snapy import netsnmp
from snapy.twisted import Session as SnmpSession

from nagcat import errors, query, util

class SNMPCommon(query.Query):
    """Parent class for both SNMPQuery and SNMPCombined."""

    def __init__(self, nagcat, conf):
        super(SNMPCommon, self).__init__(nagcat, conf)

        protocol = conf.get('protocol', 'udp')
        if protocol not in ('udp', 'tcp', 'unix'):
            raise errors.ConfigError(conf,
                    "Invalid SNMP protocol: %r" % conf['protocol'])

        # Unix sockets are used by the unit tests
        if protocol == 'unix':
            self.conf['addr'] = 'unix:%s' % conf['path']
        else:
            self.conf['addr'] = '%s:%s:%d' % (protocol,
                    self.addr, int(conf.get('port', 161)))

        self.conf['version'] = str(conf.get('version', '2c'))
        if self.conf['version'] not in ('1', '2c'):
            raise errors.ConfigError(conf,
                    "Invalid SNMP version %r" % conf['version'])

        self.conf['community'] = conf.get('community', None)
        if not self.conf['community']:
            raise errors.ConfigError(conf, "SNMP community is required")

    def check_oid(self, conf, key):
        """Check/parse an oid"""
        try:
            oid = netsnmp.OID(conf[key])
        except netsnmp.OIDValueError, ex:
            raise errors.ConfigError(conf, str(ex))

        return oid

class SNMPQuery(SNMPCommon):
    """Fetch a single value via SNMP"""

    classProvides(query.IQuery)

    name = "snmp"

    def __init__(self, nagcat, conf):
        super(SNMPQuery, self).__init__(nagcat, conf)

        if 'oid' in conf:
            if ("oid_base" in conf or "oid_key" in conf or "key" in conf):
                raise errors.ConfigError(conf,
                        "oid cannot be used with oid_base, oid_key, and key")

            self.conf['oid'] = self.check_oid(conf, 'oid')

            conf['walk'] = False
            self.query_oid = nagcat.new_query(conf, qcls=SNMPCombined)
            self.addDependency(self.query_oid)

        elif ("oid_base" in conf and "oid_key" in conf and "key" in conf):
            if "oid" in conf:
                raise errors.ConfigError(conf,
                        "oid cannot be used with oid_base, oid_key, and key")

            self.conf['oid_base'] = self.check_oid(conf, 'oid_base')
            self.conf['oid_key'] = self.check_oid(conf, 'oid_key')
            self.conf['key'] = conf['key']
            conf['walk'] = True

            base = conf.copy()
            base['oid'] = self.conf['oid_base']
            self.query_base = nagcat.new_query(base, qcls=SNMPCombined)
            self.addDependency(self.query_base)

            key = conf.copy()
            key['oid'] = self.conf['oid_key']
            self.query_key = nagcat.new_query(key, qcls=SNMPCombined)
            self.addDependency(self.query_key)
        else:
            raise errors.ConfigError(conf,
                    "oid or oid_base, oid_key, and key are required")

        if "oid_scale" in conf:
            self.conf['oid_scale'] = self.check_oid(conf, 'oid_scale')
            scale = conf.copy()
            scale['oid'] = self.conf['oid_scale']
            self.query_scale = nagcat.new_query(scale, qcls=SNMPCombined)
            self.addDependency(self.query_scale)
        else:
            self.query_scale = None

    def _start(self):
        """Get and filter the result the from combined query."""

        try:
            if "oid" in self.conf:
                return self._get_result()
            else:
                return self._get_result_set()
        except:
            return errors.Failure()

    def _do_scale(self, scale, value):
        """Scale a numeric value"""

        # Use MathString so this even works if the OID returns
        # a number as a string, uncommon but possible.
        try:
            scale = util.MathString(scale)
            value = util.MathString(value)
        except util.MathError:
            raise errors.TestCritical(
                "oid_scale is set but result(s) are not numbers")

        return value * scale

    def _get_result(self):
        """Get a single oid value"""

        result = self.query_oid.result
        if isinstance(result, failure.Failure):
            return result

        oid = self.conf['oid']
        result = dict(self.query_oid.result)
        if oid not in result:
            raise errors.TestCritical("No value received for %s" % (oid,))
        result = result[oid]

        if self.query_scale:
            oid = self.conf['scale_oid']
            scale = dict(self.query_scale.result)
            if oid not in result:
                raise errors.TestCritical("No value received for %s" % (oid,))
            scale = scale[oid]
            result = self._do_scale(scale, result)

        return str(result)

    def _get_result_set(self):
        """Get the requested value from the oid_base set.

        Matches the value index from the oid_key set specified
        by the key field to retreive the oid_base value.
        """

        class Return(Exception):
            pass

        def filter_result(result, root):
            if isinstance(result, failure.Failure):
                raise Return(result)

            new = {}
            for key, value in result:
                if key.startswith(self.conf[root]):
                    new[key] = value

            if not new:
                raise errors.TestCritical("No values received for %s" % (root,))

            return new

        try:
            base = filter_result(self.query_base.result, "oid_base")
            keys = filter_result(self.query_key.result, "oid_key")
            if self.query_scale:
                scale = filter_result(self.query_scale.result, "oid_scale")
        except Return, ex:
            return ex.args[0]

        final = None
        for oid, value in keys.iteritems():
            if value == self.conf["key"]:
                index = oid[len(self.conf["oid_key"]):]
                final = self.conf['oid_base'] + index
                if self.query_scale:
                    final_scale = self.conf['oid_scale'] + index
                break

        if final is None:
            raise errors.TestCritical("key not found: %r" % self.conf["key"])

        if final not in base:
            raise errors.TestCritical("No value received for %s" % (final,))

        result = base[final]

        if self.query_scale:
            if final_scale not in scale:
                raise errors.TestCritical(
                        "No value received for %s" % (final_scale,))
            scale = scale[final_scale]
            result = self._do_scale(scale, result)

        return str(result)


class SNMPCombined(SNMPCommon):
    """Combined Query used to send just one query to common host."""

    # For the scheduler stats
    name = "snmp_combined"

    def __init__(self, nagcat, conf):
        """Initialize query with oids and host port information."""
        super(SNMPCombined, self).__init__(nagcat, conf)

        self.oids = set()
        self.update(conf)
        self.conf['walk'] = conf['walk']

        # Don't combine version 1 queries because the response can only
        # report one error and we can't tell if the others are ok or not
        if self.conf['version'] == "1":
            self.conf['oids'] = self.oids

        try:
            self.client = SnmpSession(
                    version=self.conf['version'],
                    community=self.conf['community'],
                    # Retry after 1 second for 'timeout' retries
                    timeout=1, retrys=int(self.conf['timeout']),
                    peername=self.conf['addr'])
        except netsnmp.SnmpError, ex:
            raise errors.InitError("Snmp Error: %s" % ex)

    def update(self, conf):
        """Update compound query with oids to be retreived from host."""
        self.oids.add(self.check_oid(conf, 'oid'))

    def _start(self):
        try:
            self.client.open()
            if self.conf['walk']:
                deferred = self.client.walk(self.oids, strict=True)
            else:
                deferred = self.client.get(self.oids)
        except:
            return errors.Failure()

        deferred.addBoth(self._handle_close)
        deferred.addErrback(self._handle_error)
        return deferred

    @errors.callback
    def _handle_close(self, result):
        """Close the SNMP connection socket"""
        self.client.close()
        return result

    @errors.callback
    def _handle_error(self, result):
        if isinstance(result.value, neterror.TimeoutError):
            raise errors.TestCritical("SNMP request timeout")
        return result

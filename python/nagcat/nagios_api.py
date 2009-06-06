# Copyright 2009 ITA Software, Inc.
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

"""Nagios command writer"""

import os
import re
import time
import random

from twisted.web import xmlrpc

from nagcat import errors, log, nagios_objects

class NagiosCommander(object):

    ALLOWED_COMMANDS = {
            'DEL_HOST_DOWNTIME': 1,
            'DEL_SVC_DOWNTIME': 1,
            'PROCESS_SERVICE_CHECK_RESULT': 4,
            'SCHEDULE_HOSTGROUP_HOST_DOWNTIME': 8,
            'SCHEDULE_HOST_DOWNTIME': 8,
            'SCHEDULE_HOST_SVC_DOWNTIME': 8,
            'SCHEDULE_SERVICEGROUP_SVC_DOWNTIME': 8,
            'SCHEDULE_SVC_DOWNTIME': 9,
            }

    def __init__(self, command_file):
        self._command_file = command_file
        self._command_fd = None
        self._open_command_file()

    def _open_command_file(self):
        try:
            self._command_fd = os.open(self._command_file,
                    os.O_WRONLY | os.O_APPEND | os.O_NONBLOCK)
        except OSError, ex:
            raise errors.InitError("Failed to open command file %s: %s"
                    % (self._command_file, ex))

    def _write_command(self, data):
        try:
            os.write(self._command_fd, data)
        except (OSError, IOError):
            self._open_command_file()
            try:
                os.write(self._command_fd, data)
            except (OSError, IOError), ex:
                raise errors.InitError("Failed to write command to %s: %s"
                        % (self._command_file, ex))

    def command(self, cmd_time, cmd_name, *args):
        """Submit a command to Nagios.

        @param time: a Unix timestamp or None
        @param cmd: a Nagios command name, must be in ALLOWED_COMMANDS
        @param *args: the command arguments
        """
        if not cmd_time:
            cmd_time = time.time()
        cmd_time = int(cmd_time)

        assert cmd_name in self.ALLOWED_COMMANDS
        assert len(args) == self.ALLOWED_COMMANDS[cmd_name]

        clean_args = [cmd_name]
        for arg in args[:-1]:
            # These arguments may not contain newlines or ;
            arg = str(arg)
            assert '\n' not in arg and not ';' in arg
            clean_args.append(arg)

        # The last argument may contain newlines but they must be escaped
        # | is not allowed but likely to appear so just replace it
        if args:
            arg = args[-1].replace('\n', '\\n').replace('|', '_')
            clean_args.append(arg)

        formatted = "[%d] %s\n" % (cmd_time, ';'.join(clean_args))
        log.trace("Writing Nagios command: %s", formatted)
        self._write_command(formatted)

class NagiosXMLRPC(xmlrpc.XMLRPC):
    """A XMLRPC Protocol for Nagios"""

    EXPR_TOKEN = re.compile(r"""\s*([\w:-]+|\(|\)|"|')\s*""")

    def __init__(self, nagios_cfg):
        xmlrpc.XMLRPC.__init__(self)
        xmlrpc.addIntrospection(self)

        cfg = nagios_objects.ConfigParser(nagios_cfg,
                ('object_cache_file', 'command_file', 'status_file'))

        # object types we care about:
        types = ('host', 'service', 'hostgroup', 'servicegroup')
        rawobjs = nagios_objects.ObjectParser(cfg['object_cache_file'], types)

        self._objects = dict([(x,{}) for x in types])

        for obj in rawobjs['host']:
            self._objects['host'][obj['host_name']] = obj

        for obj in rawobjs['service']:
            host_name = obj['host_name']
            description = obj['service_description']
            if host_name not in self._objects['service']:
                self._objects['service'][host_name] = {}
            self._objects['service'][host_name][description] = obj

        for obj in rawobjs['hostgroup']:
            obj['members'] = obj['members'].split(',')
            self._objects['hostgroup'][obj['hostgroup_name']] = obj

        for obj in rawobjs['servicegroup']:
            members = []
            members_list = obj['members'].split(',')
            for i in xrange(0, len(members_list), 2):
                members.append((members_list[i], members_list[i+1]))
            obj['members'] = members
            self._objects['servicegroup'][obj['servicegroup_name']] = obj

        self._cmdobj = NagiosCommander(cfg['command_file'])
        self._status_file = cfg['status_file']

    def _cmd(self, *args):
        try:
            self._cmdobj.command(*args)
        except errors.InitError, ex:
            raise xmlrpc.Fault(1, "Command failed: %s" % ex)

    def _status(self, object_types=(), object_select=()):
        try:
            stat = nagios_objects.ObjectParser(
                    self._status_file, object_types, object_select)
        except errors.InitError, ex:
            log.error("Failed to parse Nagios status file: %s" % ex)
            raise xmlrpc.Fault(1, "Failed to read Nagios status")

        return stat

    def xmlrpc_listHosts(self):
        """get a list of host names"""
        return self._objects['host'].keys()

    def xmlrpc_getHost(self, host_name):
        """get a struct defining a host"""
        if host_name not in self._objects['host']:
            raise xmlrpc.Fault(1, "Unknown host: %r" % host_name)
        return self._objects['host'][host_name]

    def xmlrpc_listHostServices(self, host_name):
        """get a list of services on a host"""
        if host_name not in self._objects['service']:
            raise xmlrpc.Fault(1, "Unknown host: %r" % host_name)
        return self._objects['service'][host_name].keys()

    def xmlrpc_getHostService(self, host_name, service_description):
        """get a struct defining a service"""
        if host_name not in self._objects['service']:
            raise xmlrpc.Fault(1, "Unknown host: %r" % host_name)
        if service_description not in self._objects['service'][host_name]:
            raise xmlrpc.Fault(1, "Unknown service: %r" % service_description)
        return self._objects['service'][host_name][service_description]

    def xmlrpc_listHostGroups(self):
        """get a list of host groups"""
        return self._objects['hostgroup'].keys()

    def xmlrpc_getHostGroup(self, hostgroup_name):
        """get a struct defining a host group"""
        if hostgroup_name not in self._objects['hostgroup']:
            raise xmlrpc.Fault(1, "Unknown hostgroup: %r" % hostgroup_name)

    def xmlrpc_listServiceGroups(self):
        """get a list of service groups"""
        return self._objects['servicegroup'].keys()

    def xmlrpc_getServiceGroup(self, servicegroup_name):
        """get a struct defining a service group"""
        if servicegroup_name not in self._objects['servicegroup']:
            raise xmlrpc.Fault(1,
                    "Unknown servicegroup: %r" % servicegroup_name)
        return self._objects['servicegroup'][servicegroup_name]

    def xmlrpc_scheduleServiceDowntime(self, expr, start, stop, user, comment):
        """schedule service downtime

        expr: an expression defining the set to operate on
            operators:
                or (the union of two sets)
                and (the intersection of two sets)
            identifiers:
                host:hostname
                service:hostname:servicename
                hostgroup:groupname
                servicegroup:groupname

            Quotes (' or ") must be placed around service
            descriptions when they contain whitespace.
        start: date/time to start (in seconds since epoch!)
        stop: date/time to auto-cancel the downtime
        user: identifier defining who/what sent this request
        comment: arbitrary comment about the downtime
        
        returns a key to use to cancel this downtime early
        """

        return self._scheduleDowntime('service',
                expr, start, stop, user, comment)

    def xmlrpc_scheduleHostDowntime(self, expr, start, stop, user, comment):
        """schedule host downtime

        expr: an expression defining the set to operate on
            operators:
                or (the union of two sets)
                and (the intersection of two sets)
            identifiers:
                host:hostname
                service:hostname:servicename
                hostgroup:groupname
                servicegroup:groupname

            Quotes (' or ") must be placed around service
            descriptions when they contain whitespace.
        start: date/time to start (in seconds since epoch!)
        stop: date/time to auto-cancel the downtime
        user: identifier defining who/what sent this request
        comment: arbitrary comment about the downtime
        
        returns a key to use to cancel this downtime early
        """

        return self._scheduleDowntime('host',
                expr, start, stop, user, comment)

    def _scheduleDowntime(self, type_, expr, start, stop, user, comment):
        try:
            start = int(start)
            stop = int(stop)
        except:
            raise xmlrpc.Fault(1, "start/stop must be integers")

        now = int(time.time())
        key = random.randint(100, 999)
        comment += " key:%d" % key

        assert isinstance(type_, str)
        tokenizer = self._groupTokenizer(expr+')')
        group_set = self._groupParser(tokenizer, type_)

        if not group_set:
            raise xmlrpc.Fault(1, "expression evaluated to an empty set")

        if type_ == 'host':
            for host in group_set:
                self._cmd(now, 'SCHEDULE_HOST_DOWNTIME', host,
                        start, stop, 1, 0, 0, user, comment)
        else:
            for host, service in group_set:
                self._cmd(now, 'SCHEDULE_SVC_DOWNTIME', host, service,
                        start, stop, 1, 0, 0, user, comment)

        return "%d:%d" % (now, key)

    def _groupParser(self, tokenizer, return_type):
        seq = [None, None, None]
        index = 0
        for token in tokenizer:
            if index == 1:
                if token.lower() in ('and', 'or'):
                    seq[1] = token.lower()
                elif token == ')':
                    return seq[0]
                else:
                    raise xmlrpc.Fault(1, "Unexpected token: %r" % token)
            elif token == '(':
                seq[index] = self._groupParser(tokenizer, return_type)
            else:
                seq[index] = self._groupGetSet(token, return_type)

            if index == 2:
                if seq[1] == 'and':
                    seq[0].intersection_update(seq[2])
                elif seq[1] == 'or':
                    seq[0].update(seq[2])
                index = 1
            else:
                index += 1

        raise xmlrpc.Fault(1, "Unexpected end of expression")

    def _groupGetSet(self, identifier, return_type):
        if ':' not in identifier:
            raise xmlrpc.Fault(1, "Invalid identifier: %r" % name)

        group_type, group_name = identifier.split(':', 1)

        if group_type == 'host':
            if group_name not in self._objects['host']:
                raise xmlrpc.Fault(1, "Unknown host: %r" % group_name)

            if return_type == 'host':
                group_set = [group_name]
            else:
                group_set = []
                for service in self._objects['service'].get(group_name, []):
                    group_set.append((group_name, service))

        elif group_type == 'service':
            if ':' not in group_name:
                raise xmlrpc.Fault(1, "Invalid service: %r" % group_name)

            host_name, service = group_name.split(':', 1)

            if host_name not in self._objects['service']:
                raise xmlrpc.Fault(1, "Unknown host: %r" % host_name)
            if service not in self._objects['service'][host_name]:
                raise xmlrpc.Fault(1, "Unknown service: %r" % service)

            if return_type == 'host':
                group_set = [host_name]
            else:
                group_set = [(host_name, service)]

        elif group_type == 'hostgroup':
            if group_name not in self._objects['hostgroup']:
                raise xmlrpc.Fault(1, "Unknown hostgroup: %r" % group_name)

            hosts = self._objects['hostgroup'][group_name]['members']
            if return_type == 'host':
                group_set = hosts
            else:
                group_set = []
                for host_name in hosts:
                    services = self._objects['service'].get(host_name,[])
                    group_set.extend([(host_name, x) for x in services])

        elif group_type == 'servicegroup':
            if group_name not in self._objects['servicegroup']:
                raise xmlrpc.Fault(1, "Unknown servicegroup: %r" % group_name)

            group_set = self._objects['servicegroup'][group_name]['members']
            if return_type == 'host':
                group_set = [x[0] for x in group_set]

        else:
            raise xmlrpc.Fault(1, "Unknown type: %r" % group_type)

        return set(group_set)

    def _groupTokenizer(self, string):
        while True:
            match = self.EXPR_TOKEN.match(string)
            if match and match.group(1) in ('"', "'"):
                try:
                    end = string.index(match.end, match.group(1))
                except ValueError:
                    raise xmlrpc.Fault(1, "Unterminated string: %s" % string)
                token = string[match.end():end]
                string = string[end+1:]
                yield token
            elif match:
                string = string[match.end():]
                yield match.group(1)
            elif string.strip():
                raise xmlrpc.Fault(1, "Unexpected token: %s" % string)
            else:
                break

    def xmlrpc_delServiceDowntime(self, key):
        """Cancel all service downtimes identified by key"""

        return self._delDowntime('servicedowntime', 'DEL_SVC_DOWNTIME', key)

    def xmlrpc_delHostDowntime(self, key):
        """Cancel all host downtimes identified by key"""

        return self._delDowntime('hostdowntime', 'DEL_HOST_DOWNTIME', key)

    def _delDowntime(self, objtype, cmdtype, key):
        try:
            timestamp, uid = key.split(':', 1)
            assert int(timestamp) and int(uid)
        except:
            raise xmlrpc.Fault(1, "Invalid downtime key: %r" % key)

        status = self._status([objtype], {'entry_time': timestamp})
        count = 0

        for downtime in status[objtype]:
            if downtime['comment'].endswith('key:%s' % uid):
                self._cmd(None, cmdtype, downtime['downtime_id'])
                count += 1

        return count

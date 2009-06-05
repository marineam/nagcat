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
import time
import random

from twisted.web import xmlrpc

from nagcat import errors, log, nagios_objects

class NagiosCommander(object):

    ALLOWED_COMMANDS = {
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

    def __init__(self, nagios_cfg):
        xmlrpc.XMLRPC.__init__(self)
        xmlrpc.addIntrospection(self)

        cfg = nagios_objects.ConfigParser(nagios_cfg)

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
        print "running.."

    def _cmd(self, *args):
        try:
            self._cmdobj.command(*args)
        except errors.InitError, ex:
            raise xmlrpc.Fault(1, "Command failed: %s" % ex)

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

    def xmlrpc_scheduleServiceDowntime(self, host_name,
            service_description, start, stop, user, comment):
        """schedule a service downtime
        
        host_name: a single host or a list of hosts
        service_description: a single service, list, or empty for all
        start: date/time to start (in seconds since epoch!)
        stop: date/time to auto-cancel the downtime
        user: identifier defining who/what sent this request
        comment: arbitrary comment about the downtime

        returns a key to use to cancel this downtime early
        """

        try:
            start = int(start)
            stop = int(stop)
        except:
            raise xmlrpc.Fault(1, "start/stop must be integers")

        now = int(time.time())
        key = random.randint(100, 999)
        comment += " key:%d" % key

        if isinstance(host_name, str):
            host_name = [host_name]
        if not service_description:
            service_description = None
        elif isinstance(service_description, str):
            service_description = [service_description]

        for host in host_name:
            if host not in self._objects['host']:
                raise xmlrpc.Fault(1, "Unknown host: %r" % host)

            for service in service_description:
                if service not in self._objects['service'][host]:
                    raise xmlrpc.Fault(1, "Unknown service: %r / %r" %
                            (host, service))

        for host in host_name:
            if service_description is None:
                self._cmd(now, 'SCHEDULE_HOST_SVC_DOWNTIME',
                        host, start, stop, 1, 0, 0, user, comment)
            else:
                for service in service_description:
                    self._cmd(now, 'SCHEDULE_SVC_DOWNTIME', host,
                            service, start, stop, 1, 0, 0, user, comment)

        return "%d:%d" % (now, key)

    def xmlrpc_scheduleServiceUnionDowntime(self, groups,
            start, stop, user, comment):
        """schedule service downtime for a group

        group: a single group or a list, downtime will be set for the
            union of the listed service groups.
        start: date/time to start (in seconds since epoch!)
        stop: date/time to auto-cancel the downtime
        user: identifier defining who/what sent this request
        comment: arbitrary comment about the downtime
        """

        return self._scheduleServiceGroupDowntime(False,
                groups, start, stop, user, comment)

    def xmlrpc_scheduleServiceIntersectDowntime(self, groups,
            start, stop, user, comment):
        """schedule service downtime for a group

        group: a single group or a list, downtime will be set for the
            intersection of the listed service groups.
        start: date/time to start (in seconds since epoch!)
        stop: date/time to auto-cancel the downtime
        user: identifier defining who/what sent this request
        comment: arbitrary comment about the downtime
        """

        return self._scheduleServiceGroupDowntime(True,
                groups, start, stop, user, comment)

    def _scheduleServiceGroupDowntime(self, intersect, groups,
            start, stop, user, comment):
        try:
            start = int(start)
            stop = int(stop)
        except:
            raise xmlrpc.Fault(1, "start/stop must be integers")

        now = int(time.time())
        key = random.randint(100, 999)
        comment += " key:%d" % key

        if isinstance(groups, str):
            groups = [groups]

        for group in groups:
            if group not in self._objects['servicegroup']:
                raise xmlrpc.Fault(1, "Unknown servicegroup: %r" % group)


        if len(groups) == 1:
            self._cmd(now, 'SCHEDULE_SERVICEGROUP_SVC_DOWNTIME',
                    groups[0], start, stop, 1, 0, 0, user, comment)
        else:
            final_services = set(
                    self._objects['servicegroup'][groups[0]]['members'])
            for group in groups[1:]:
                new_services = set(
                        self._objects['servicegroup'][group]['members'])
                if intersect:
                    final_services.intersection_update(new_services)
                else:
                    final_services.update(new_services)

            if not final_services:
                raise xmlrpc.Fault(1, "Group intersection contains no services")

            for service in final_services:
                self._cmd(now, 'SCHEDULE_SVC_DOWNTIME', service[0],
                        service[1], start, stop, 1, 0, 0, user, comment)

        return "%d:%d" % (now, key)

    def xmlrpc_scheduleHostDowntime(self, host_name,
            start, stop, user, comment):
        """schedule a host downtime
        
        host_name: a single host or a list of hosts
        start: date/time to start (in seconds since epoch!)
        stop: date/time to auto-cancel the downtime
        user: identifier defining who/what sent this request
        comment: arbitrary comment about the downtime

        returns a key to use to cancel this downtime early
        """

        try:
            start = int(start)
            stop = int(stop)
        except:
            raise xmlrpc.Fault(1, "start/stop must be integers")

        now = int(time.time())
        key = random.randint(100, 999)
        comment += " key:%d" % key

        if isinstance(host_name, str):
            host_name = [host_name]

        for host in host_name:
            if host not in self._objects['host']:
                raise xmlrpc.Fault(1, "Unknown host: %r" % host)

        for host in host_name:
            self._cmd(now, 'SCHEDULE_HOST_DOWNTIME',
                    host, start, stop, 1, 0, 0, user, comment)

        return "%d:%d" % (now, key)

    def xmlrpc_scheduleHostUnionDowntime(self, groups,
            start, stop, user, comment):
        """schedule host downtime for a group

        group: a single group or a list, downtime will be set for the
            union of the listed service groups.
        start: date/time to start (in seconds since epoch!)
        stop: date/time to auto-cancel the downtime
        user: identifier defining who/what sent this request
        comment: arbitrary comment about the downtime
        """

        return self._scheduleHostGroupDowntime(False,
                groups, start, stop, user, comment)

    def xmlrpc_scheduleHostIntersectDowntime(self, groups,
            start, stop, user, comment):
        """schedule host downtime for a group

        group: a single group or a list, downtime will be set for the
            intersection of the listed service groups.
        start: date/time to start (in seconds since epoch!)
        stop: date/time to auto-cancel the downtime
        user: identifier defining who/what sent this request
        comment: arbitrary comment about the downtime
        """

        return self._scheduleHostGroupDowntime(True,
                groups, start, stop, user, comment)

    def _scheduleHostGroupDowntime(self, intersect, groups,
            start, stop, user, comment):
        try:
            start = int(start)
            stop = int(stop)
        except:
            raise xmlrpc.Fault(1, "start/stop must be integers")

        now = int(time.time())
        key = random.randint(100, 999)
        comment += " key:%d" % key

        if isinstance(groups, str):
            groups = [groups]

        for group in groups:
            if group not in self._objects['hostgroup']:
                raise xmlrpc.Fault(1, "Unknown hostgroup: %r" % group)

        if len(groups) == 1:
            self._cmd(now, 'SCHEDULE_HOSTGROUP_HOST_DOWNTIME',
                    groups[0], start, stop, 1, 0, 0, user, comment)
        else:
            final_hosts = set(
                    self._objects['hostgroup'][groups[0]]['members'])
            for group in groups[1:]:
                new_hosts = set(
                        self._objects['hostgroup'][group]['members'])
                if intersect:
                    final_hosts.intersection_update(new_hosts)
                else:
                    final_hosts.update(new_hosts)

            if not final_hosts:
                raise xmlrpc.Fault(1, "Group intersection contains no hosts")

            for host in final_hosts:
                self._cmd(now, 'SCHEDULE_HOST_DOWNTIME', host,
                        start, stop, 1, 0, 0, user, comment)

        return "%d:%d" % (now, key)

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
import stat
import shlex
import struct
import base64
import random
import tempfile
import cStringIO
from collections import deque

from twisted.web import xmlrpc
from twisted.internet import reactor, interfaces
from twisted.python.log import Logger
from twisted.python import failure
from zope.interface import implements

from nagcat import errors, log, nagios_objects

def spool_path(nagios_spool, name):
    nagios_spool = os.path.abspath(nagios_spool)
    dir = os.path.dirname(nagios_spool)
    spool = "%s/%s" % (dir, name)
    return spool

class NagiosWriter(Logger, object):
    """Writes out data to fd pipe file when available."""

    implements(interfaces.IWriteDescriptor)

    CLEANUP = re.compile('\[\d+\] PROCESS_FILE;([^;]+);1\s*')
    MAXSIZE = 10000

    def __init__(self, filename):
        """Initialize writer with a file descriptor."""

        self._data = None
        self._data_queue = deque()
        self._file = filename
        self._fd = None
        self._timer = None

        try:
            self._open_file()
        except OSError, (errno, errmsg):
            raise errors.InitError("Failed to open nagios pipe %s: %s"
                    % (self._file, errmsg))

        reactor.addSystemEventTrigger('after', 'shutdown', self.shutdown)

    def fileno(self):
        """Returns the file descriptor."""
        return self._fd

    def connectionLost(self, reason):
        """Gracefully try to reopen the connection."""

        if reactor.running:
            self._reopen_file()
        else:
            self._close_file()

    def doWrite(self):
        """Write data out to the pipe."""

        while self._data or self._data_queue:
            if not self._data:
                self._data = self._data_queue.popleft()

            log.trace("Writing Nagios command to fifo: %s", self._data)

            try:
                data_written = os.write(self._fd, self._data)
            except OSError, (errno, errmsg):
                if errno == 11:
                    # EAGAIN, pause writing until next doWrite()
                    return
                else:
                    log.warn("Failed to write to nagios pipe: %s" % errmsg)
                    self._reopen_file()
                    return

            if len(self._data) != data_written:
                self._data = self._data[data_written:]
                return
            else:
                self._data = None

        self.stopWriting()

    def startWriting(self):
        """Add writer to the reactor"""
        if self._fd is not None:
            reactor.addWriter(self)

    def stopWriting(self):
        """Remove writer from the reactor"""
        reactor.removeWriter(self)

    def write(self, data):
        """Adding data to the data_queue to be sent into the pipe."""

        if len(self._data_queue) >= self.MAXSIZE:
            self._cleanup()

        self._data_queue.append(data)
        self.startWriting()

    def shutdown(self):
        """Remove any unused spool files"""
        if self._data_queue:
            log.info("Removing unsubmitted results")

            while self._data_queue:
                self._cleanup()

    def _cleanup(self):
        """Drop a command, clean up the temp file if needed."""
        match = self.CLEANUP.match(self._data_queue.popleft())
        if match and os.path.exists(match.group(1)):
            os.unlink(match.group(1))

    def _reopen_file(self):
        """Attempt to reopen the pipe."""

        if self._timer:
            if not self._timer.called:
                self._timer.cancel()
            self._timer = None

        try:
            self._open_file()
        except OSError, (errno, errmsg):
            log.warn("Failed to reopen nagios pipe: %s" % errmsg)
            self._timer = reactor.callLater(10.0, self._reopen_file)
        else:
            log.info("Reopened nagios pipe, resuming writes.")

    def _open_file(self):
        """Open a named pipe file for writing."""
        self._close_file()
        self._fd = os.open(self._file, os.O_WRONLY | os.O_NONBLOCK)
        self.startWriting()

    def _close_file(self):
        """Close the named pipe if open"""

        if self._fd is not None:
            self.stopWriting()
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None


class NagiosCommander(object):

    ALLOWED_COMMANDS = {
            'DEL_HOST_DOWNTIME': 1,
            'DEL_SVC_DOWNTIME': 1,
            'PROCESS_FILE': 2,
            'PROCESS_SERVICE_CHECK_RESULT': 4,
            'SCHEDULE_HOSTGROUP_HOST_DOWNTIME': 8,
            'SCHEDULE_HOST_DOWNTIME': 8,
            'SCHEDULE_HOST_SVC_DOWNTIME': 8,
            'SCHEDULE_SERVICEGROUP_SVC_DOWNTIME': 8,
            'SCHEDULE_SVC_DOWNTIME': 9,
            }

    # This must stay in sync with the define in nagios' common.h
    # I'm setting it to a bit below the limit just to be safe.
    MAX_EXTERNAL_COMMAND_LENGTH = 8180

    ESCAPE = re.compile(r'(\\|\n|\|)')

    def __init__(self, command_file, spool_dir):
        """Create writer and add it to the reactor.

        command_file is the path to the nagios pipe
        spool_dir is where to write large commands to
        """

        self.spool_dir = spool_dir
        # Create or cleanup the spool dir
        if os.path.isdir(spool_dir):
            self._cleanup_spool()
        else:
            assert not os.path.exists(spool_dir)
            try:
                os.makedirs(spool_dir)
            except OSError, ex:
                raise errors.InitError(
                        "Cannot create directory %s: %s" % (spool_dir, ex))

        info = os.stat(command_file)
        if not stat.S_ISFIFO(info.st_mode):
            raise errors.InitError(
                    "Command file %s is not a fifo" % command_file)

        self.writer = NagiosWriter(command_file)

    def command(self, cmd_time, *args):
        """Submit a command to Nagios.

        @param cmd_time: a Unix timestamp or None
        @param *args: the command name and its arguments arguments
        """
        self.cmdlist(cmd_time, [args])

    def cmdlist(self, cmd_time, cmd_list, force=False):
        """Submit a list of commands to Nagios.

        @param cmd_time: a Unix timestamp or None
        @param cmd_list: a sequence of (comandname, arg1...) tuples
        @param force: run the commands now rather than in a thread
        """

        if not cmd_time:
            cmd_time = time.time()
        cmd_time = int(cmd_time)

        if force:
            self._threaded_command(cmd_time, cmd_list, True)
        else:
            reactor.callInThread(self._threaded_command, cmd_time, cmd_list)

    def _threaded_command(self, cmd_time, cmd_list, force=False):
        """Write out out the temporary command file from a thread to
        avoid any momentary delays that may be caused by creating
        creating the file.
        """

        spool_fd, spool_path = tempfile.mkstemp(dir=self.spool_dir)
        try:
            try:
                for cmd in cmd_list:
                    text = self._format_command(cmd_time, *cmd)
                    log.trace("Writing Nagios command to spool: %s", text)
                    os.write(spool_fd, text)

                submit = self._format_command(cmd_time,
                        'PROCESS_FILE', spool_path, '1')
                if force:
                    self.writer.write(submit)
                    self.writer.doWrite()
                else:
                    reactor.callFromThread(self.writer.write, submit)
            except:
                os.unlink(spool_path)
                raise
        finally:
            os.close(spool_fd)

    def _format_command(self, cmd_time, cmd_name, *args):
        assert cmd_name in self.ALLOWED_COMMANDS
        assert len(args) == self.ALLOWED_COMMANDS[cmd_name]

        clean_args = [cmd_name]
        for arg in args[:-1]:
            # These arguments may not contain newlines or ;
            arg = str(arg)
            assert '\n' not in arg and not ';' in arg
            clean_args.append(arg)

        # The last argument may contain newlines but they must be escaped
        # | is not allowed at all so we use \_ as an escape sequence.
        def escape(match):
            char = match.group(1)
            if char == '\\':
                return r'\\'
            elif char == '\n':
                return r'\n'
            elif char == '|':
                return r'\_'
            else:
                assert 0

        if args:
            arg = self.ESCAPE.sub(escape, args[-1])
            # Workaround a bug in some Nagios versions
            arg.rstrip('\\')
            clean_args.append(arg)

        formatted = "[%d] %s\n" % (cmd_time, ';'.join(clean_args))

        # Nagios gets grumpy when you give it too much text
        if len(formatted) >= self.MAX_EXTERNAL_COMMAND_LENGTH:
            formatted = formatted[:self.MAX_EXTERNAL_COMMAND_LENGTH-1]
            formatted = formatted.rstrip('\\')
            formatted = "%s\n" % formatted

        return formatted

    def _cleanup_spool(self):
        """Periodically clean up old things in the spool dir.

        This shouldn't normally be required but if things get screwed
        up we don't want the directory to get so huge that it keeps
        things slow after nagios is handling results again.
        """

        # Note: It is entirely possible that the command to submit
        # this file is still in the writer queue, if that's the case
        # nagios will also log an error when it gets around to
        # reading from the queue.

        # Set the threshold to 5 minutes ago, if nagios hasn't been
        # able to keep up for the past 5 minutes we have problems.
        threshold = time.time() - 300
        count = 0
        for item in os.listdir(self.spool_dir):
            path = "%s/%s" % (self.spool_dir, item)
            try:
               info = os.stat(path)
            except:
                continue
            if info.st_mtime < threshold:
                try:
                    os.unlink(path)
                except OSError, ex:
                    log.error("Failed to remove %s: %s" % (path, ex))
                else:
                    count += 1

        if count:
            log.warn("Removed %d stale nagios command files" % count)

        # Schedule the next cleanup to run from a thread in 1 minute
        reactor.callLater(60, reactor.callInThread, self._cleanup_spool)


class NagiosXMLRPC(xmlrpc.XMLRPC):
    """A XMLRPC Protocol for Nagios"""

    def __init__(self, nagios_cfg):
        xmlrpc.XMLRPC.__init__(self)
        xmlrpc.addIntrospection(self)

        cfg = nagios_objects.ConfigParser(nagios_cfg,
                ('object_cache_file', 'command_file',
                 'status_file', 'check_result_path'))

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
            if obj.get('members', None):
                obj['members'] = obj['members'].split(',')
            else:
                obj['members'] = []
            self._objects['hostgroup'][obj['hostgroup_name']] = obj

        for obj in rawobjs['servicegroup']:
            members = []
            if obj.get('members', None):
                members_list = obj['members'].split(',')
                for i in xrange(0, len(members_list), 2):
                    members.append((members_list[i], members_list[i+1]))
            obj['members'] = members
            self._objects['servicegroup'][obj['servicegroup_name']] = obj

        spool = spool_path(cfg['check_result_path'], 'xmlrpc')
        self._cmdobj = NagiosCommander(cfg['command_file'], spool)
        self._status_file = cfg['status_file']

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

    def xmlrpc_listDowntimes(self):
        """Get a list of currently scheduled downtimes"""

        regex = re.compile('^(.*)\skey:(\S+)(\s+expr:(.+))?$')
        def parse_comment(downtime):
            match = regex.match(downtime['comment'])
            if not match:
                downtime['key'] = None
                downtime['expr'] = None
                return

            downtime['comment'] = match.group(1)
            key = match.group(2)
            if len(key) == 3 and key.isdigit():
                downtime['key'] = "%s:%s" % (downtime['entry_time'], key)
            else:
               downtime['key'] = key
            if match.group(3):
                downtime['expr'] = match.group(4)
            else:
                downtime['expr'] = ""

        status = self._status(('hostdowntime', 'servicedowntime'))
        result = {'host': status['hostdowntime'],
                  'service': status['servicedowntime'] }

        for dtype in result.itervalues():
            for downtime in dtype:
                parse_comment(downtime)

        return result

    def xmlrpc_scheduleServiceDowntime(self, expr, start, stop, user, comment):
        """Alias for scheduleDowntime"""

        return self.xmlrpc_scheduleDowntime(expr, start, stop, user, comment)

    def xmlrpc_scheduleHostDowntime(self, expr, start, stop, user, comment):
        """Alias for scheduleDowntime"""

        return self.xmlrpc_scheduleDowntime(expr, start, stop, user, comment)

    def xmlrpc_scheduleDowntime(self, expr, start, stop, user, comment):
        """schedule host and service downtimes

        expr: an expression defining the set to operate on
            operators:
                or (the union of two sets)
                and (the intersection of two sets)
            identifiers:
                host:hostname
                service:servicename
                hostgroup:groupname
                servicegroup:groupname

            Quotes (' or ") must be placed around service names
            when they contain whitespace.

            If a name contains any of the characters []?*+^$ it
            will be treated as a regular expression, otherwise it
            must be an exact match.

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
        key = base64.urlsafe_b64encode(struct.pack('ib',
                now, random.randint(-127,127))).strip('=')
        comment += ' key:%s expr:%s' % (key, expr.strip())

        tokenizer = self._groupTokenizer(expr+')')
        group_set = self._groupParser(tokenizer)

        if not group_set:
            raise xmlrpc.Fault(1, "expression evaluated to an empty set")

        commands = set()
        for item in group_set:
            if item[0] == 'host':
                commands.add(('SCHEDULE_HOST_DOWNTIME', item[1],
                        start, stop, 1, 0, 0, user, comment))
            elif item[0] == 'service':
                commands.add(('SCHEDULE_SVC_DOWNTIME', item[1], item[2],
                        start, stop, 1, 0, 0, user, comment))
            else:
                assert 0

        log.info("Scheduling %s downtimes in Nagios" % len(commands))
        self._cmdobj.cmdlist(now, commands)

        return key

    def _groupParser(self, tokenizer):
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
                seq[index] = self._groupParser(tokenizer)
            else:
                seq[index] = self._groupGetSet(token)

            if index == 2:
                if seq[1] == 'and':
                    seq[0] = self._groupIntersection(seq[0], seq[2])
                elif seq[1] == 'or':
                    seq[0].update(seq[2])
                index = 1
            else:
                index += 1

        raise xmlrpc.Fault(1, "Unexpected end of expression")

    def _groupIntersection(self, a, b):
        """Taking an intersection across hosts and services
        is awkward because they are different and yet related...

        We want to be able to do things like:
            hostgroup:a and (host:b or service:c)
            (host outage for b and service outage for c if they are in a)

        Or:
            host:b and service:c
            (service outage for c if it is on host b)

        Clear as mud? It should generally just do what humans expect,
        if there is a weird corner case where this function doesn't
        do what people expect (and that is a reasonable exception)
        we should figure out how to make it "just work".
        """

        host_a = set(x for x in a if x[0] == 'host')
        host_b = set(x for x in b if x[0] == 'host')
        service_a = a - host_a
        service_b = b - host_b

        def intersect_service(host1, service1, service2):
            """Intersection of services.

            Both hosts and services of the other set are considered.
            For a service to make it from service2 to the return value
            it must match a host or service in host1/service1 set.
            """
            hosts = set(x[1] for x in host1)
            serviceh = set(x for x in service2 if x[1] in hosts)
            services = service1.intersection(service2)
            return serviceh.union(services)

        # Intersect the host lists
        hosts = host_a.intersection(host_b)

        # Intersect the service lists
        services = set()
        services.update(intersect_service(host_b, service_b, service_a))
        services.update(intersect_service(host_a, service_a, service_b))

        # Now recombine them
        return hosts.union(services)

    def _groupGetSet(self, identifier):
        if ':' not in identifier:
            raise xmlrpc.Fault(1, "Invalid identifier: %r" % identifier)

        group_type, group_name = identifier.split(':', 1)
        group_set = set()

        if re.search(r'[\[\]?*+^$]', group_name):
            try:
               regex = re.compile(group_name)
               match = regex.match
            except re.error, ex:
                raise xmlrpc.Fault(1,
                        "Invalid regex %r: %s" % (group_name, ex))
        else:
            match = lambda x: x == group_name

        if group_type == 'host':
            group_set.update(('host', x)
                    for x in self._objects['host']
                        if match(x))
        elif group_type == 'service':
            for host_name in self._objects['service']:
                group_set.update(('service', host_name, x)
                        for x in self._objects['service'][host_name]
                            if match(x))
        elif group_type == 'hostgroup':
            for group, info in self._objects['hostgroup'].iteritems():
                if match(group):
                    group_set.update(('host', x)
                            for x in info.get('members', ()))
        elif group_type == 'servicegroup':
            for group, info in self._objects['servicegroup'].iteritems():
                if match(group):
                    group_set.update(('service', x[0], x[1])
                            for x in info.get('members', ()))
        else:
            raise xmlrpc.Fault(1, "Unknown type: %r" % group_type)

        if not group_set:
            raise xmlrpc.Fault(1, "Unknown %s: %r" % (group_type, group_name))

        return group_set

    def _groupTokenizer(self, string):
        string = cStringIO.StringIO(string)
        lex = shlex.shlex(string, posix=True)
        lex.escape = ""
        lex.wordchars = (
            "abcdfeghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789_.-:[]?*+^$" )
        valid = lex.wordchars + "()"

        while True:
            try:
                token = lex.get_token()
            except ValueError, ex:
                raise xmlrpc.Fault(1, "Invalid expression: %s" % ex)

            if token is lex.eof:
                break

            if len(token) == 1 and token not in valid:
                raise xmlrpc.Fault(1, "Unexpected character: %s" % token)

            yield token

    def xmlrpc_delServiceDowntime(self, key, delay=None):
        """Alias for cancelDowntime"""
        return self.xmlrpc_cancelDowntime(key, delay)

    def xmlrpc_delHostDowntime(self, key, delay=None):
        """Alias for cancelDowntime"""
        return self.xmlrpc_cancelDowntime(key, delay)

    def xmlrpc_cancelDowntime(self, key, delay=None):
        """Cancel a requested service or host downtime.

        This function searches for anything with the requested key.
        If key = 'iOkTS3Y' then anything with 'key:iOkTS3Y' will
        be canceled. The key must be an exact match. The older
        timestamp:uid format is also supported for compatibility.

        delay is a time to sleep before submitting the command to
        nagios. NOTE: if the daemon is shut-down gracefully before
        delay expires it will submit the command immediately. If
        the daemon is shutdown hard (SIGKILL, etc) the pending
        commands will be lost.
        """

        key = key.strip()

        if ':' in key:
            try:
                timestamp, key = key.split(':', 1)
                assert int(timestamp) and int(key)
            except:
                raise xmlrpc.Fault(1, "Invalid downtime key: %r" % key)

            status = self._status(('hostdowntime', 'servicedowntime'),
                                  {'entry_time': timestamp})
        else:
            status = self._status(('hostdowntime', 'servicedowntime'))

        regex = re.compile('\skey:%s(\s|$)' % key)
        match = lambda x: regex.search(x['comment'])

        commands = set()
        commands.update(('DEL_HOST_DOWNTIME', x['downtime_id'])
                for x in status['hostdowntime'] if match(x))
        commands.update(('DEL_SVC_DOWNTIME', x['downtime_id'])
                for x in status['servicedowntime'] if match(x))

        if not commands:
            return 0

        del status

        # We want to run later or at shutdown, whichever comes first.
        # This really seems like a thing that should be in twisted
        # but I didn't see anything. Oh well.
        calls = {'timer': None, 'shutdown': None}

        def do_cmd(force=False):
            calls['shutdown'] = None
            calls['timer'] = None
            log.info("Canceling %s downtimes in Nagios" % len(commands))
            self._cmdobj.cmdlist(None, commands, force)

        def do_timer():
            reactor.removeSystemEventTrigger(calls['shutdown'])
            do_cmd()

        def do_shutdown():
            calls['timer'].cancel()
            # This should not abort the daemon shutdown
            try:
                do_cmd(force=True)
            except:
                fail = failure.failure()
                log.error(fail)

        if delay:
            calls['timer'] = reactor.callLater(delay, do_timer)
            calls['shutdown'] = reactor.addSystemEventTrigger(
                    'before', 'shutdown', do_shutdown)
        else:
            do_cmd()

        return len(commands)

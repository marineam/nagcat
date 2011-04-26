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

"""Subprocess Queries"""

import os
import re
import signal

from zope.interface import classProvides
from twisted.internet import reactor, defer, protocol, process
from twisted.internet import error as neterror

from nagcat import errors, log, query


class SubprocessProtocol(protocol.ProcessProtocol):
    """Handle input/output for subprocess queries"""

    timedout = False

    def connectionMade(self):
        self.result = ""
        if self.factory.conf['data']:
            self.transport.write(self.factory.conf['data'])
        self.transport.closeStdin()

    def outReceived(self, data):
        self.result += data

    def errReceived(self, data):
        key = "Process stderr"
        self.factory.saved[key] = self.factory.saved.get(key, "") + data

    def timeout(self):
        self.timedout = True
        self.transport.loseConnection()
        # Kill all processes in the child's process group
        if self.transport.pid:
            try:
                os.kill(-int(self.transport.pid), signal.SIGTERM)
            except OSError, ex:
                log.warn("Failed to send TERM to a subprocess: %s", ex)

    def processEnded(self, reason):
        if isinstance(reason.value, neterror.ProcessDone):
            result = self.result
        elif isinstance(reason.value, neterror.ProcessTerminated):
            if self.timedout:
                result = errors.Failure(errors.TestCritical(
                    "Timeout waiting for command to finish."),
                    result=self.result)
            elif reason.value.exitCode == 127:
                result = errors.Failure(errors.TestCritical(
                    "Command not found."))
            else:
                result = errors.Failure(reason.value, result=self.result)
        else:
            result = reason

        self.factory.result(result)

class SubprocessFactory(process.Process):
    """Execute a subprocess"""

    def __init__(self, query):
        self.conf = query.conf
        self.saved = query.saved
        self.deferred = defer.Deferred()
        self._startProcess(("/bin/sh", "-c", self.conf['command']))

    def _startProcess(self, command):
        command = [str(x) for x in command]
        log.debug("Running process: %s", command)

        proto = SubprocessProtocol()
        proto.factory = self

        # Setup timeout
        call_id = reactor.callLater(self.conf['timeout'], proto.timeout)
        self.deferred.addBoth(self._cancelTimeout, call_id)

        # Setup shutdown cleanup
        call_id = reactor.addSystemEventTrigger('after', 'shutdown',
                proto.timeout)
        self.deferred.addBoth(self._cancelCleanup, call_id)

        process.Process.__init__(self, reactor, command[0], command,
                self.conf['environment'], path=None, proto=proto)

    def result(self, result):
        self.deferred.callback(result)

    def _cancelTimeout(self, result, call_id):
        if call_id.active():
            call_id.cancel()
        return result

    def _cancelCleanup(self, result, call_id):
        reactor.removeSystemEventTrigger(call_id)
        return result

    def _setupChild(self, *args, **kwargs):
        # called in the child fork, set new process group
        os.setpgrp()
        process.Process._setupChild(self, *args, **kwargs)

class SubprocessQuery(query.Query):
    """Query that runs a command"""

    classProvides(query.IQuery)

    name = "subprocess"

    def __init__(self, nagcat, conf):
        super(SubprocessQuery, self).__init__(nagcat, conf)

        env = os.environ.copy()
        if 'environment' in conf:
            env.update(conf['environment'])

        self.conf['command'] = conf['command']
        self.conf['data'] = conf.get('data', "")
        self.conf['environment'] = env

    def _start(self):
        proc = SubprocessFactory(self)
        proc.deferred.addErrback(self._checkError)
        return proc.deferred

    def _checkError(self, reason):
        if isinstance(reason.value, neterror.ProcessTerminated):
            return errors.Failure(errors.TestCritical(
                    reason.value.args[0]), result=reason.result)
        else:
            return reason

class NagiosPluginQuery(SubprocessQuery):
    """Query that runs a command"""

    classProvides(query.IQuery)

    name = "nagios_plugin"

    # 'label'=value[UOM];[warn];[crit];[min];[max]
    # where UOM (unit of measure) will usually be:
    #   a. no unit specified - assume a number (int or float) of things
    #   b. s - seconds (also us, ms)
    #   c. % - percentage
    #   d. B - bytes (also KB, MB, TB)
    #   e. c - a continous counter
    # See http://nagiosplug.sourceforge.net/developer-guidelines.html
    perf_format = re.compile(r'''(?P<label>\S+)=
                                (?P<value>[^;]*)
                                (;(?P<warn>[^;]*)
                                (;(?P<crit>[^;]*)
                                (;(?P<min>[^;]*)
                                (;(?P<max>[^;]*))?)?)?)?''', re.X)

    def __init__(self, nagcat, conf):
        super(NagiosPluginQuery, self).__init__(nagcat, conf)

        # don't pass stuff in on stdin
        self.conf['data'] = ''

        # Should we grab perf data or text? (empty means text)
        self.conf['perfdata'] = str(conf.get('perfdata', ''))

    def _start(self):
        proc = SubprocessFactory(self)
        proc.deferred.addErrback(self._checkError)
        proc.deferred.addCallback(self._parseOutput)
        return proc.deferred

    @errors.callback
    def _parseOutput(self, result):
        if not isinstance(result, basestring):
            return result

        # grab performance data from the first line
        lines = result.split('\n', 1)
        split = lines[0].split('|', 1)

        if self.conf['perfdata']:
            if len(split) != 2:
                raise errors.Critical("No performance data found")

            for match in self.perf_format.finditer(split[1]):
                if match.group('label') == self.conf['perfdata']:
                    return match.group('value')

            raise errors.Critical("No performance data found for %s" %
                                    (self.conf['perfdata'],))
        else:
            # Return the text sans perf data
            return split[0] + '\n'.join(lines[1:])

    def _checkError(self, reason):
        if isinstance(reason.value, neterror.ProcessTerminated):
            parsed = self._parseOutput(reason.result)
            if isinstance(parsed, errors.Failure):
                return parsed

            if reason.value.exitCode == 1:
                return errors.Failure(errors.TestWarning(
                    reason.result.split('\n', 1)[0]), result=parsed)
            elif reason.value.exitCode == 2:
                return errors.Failure(errors.TestCritical(
                    reason.result.split('\n', 1)[0]), result=parsed)
            elif reason.value.exitCode == 3:
                return errors.Failure(errors.TestUnknown(
                    reason.result.split('\n', 1)[0]), result=parsed)
            else:
                return errors.Failure(errors.TestUnknown(
                    reason.value.args[0]), result=parsed)
        else:
            return reason

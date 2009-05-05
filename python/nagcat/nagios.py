# Copyright 2008-2009 ITA Software, Inc.
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

"""NagCat->Nagios connector"""

from twisted.internet import reactor

from nagcat import test, util, log

class NagiosTests(object):
    """Setup tests defined by Nagios and report back"""

    def __init__(self, templates, nagios_cfg):
        """Read given Nagios config file"""

        self._nagios_obj = None
        self._nagios_cmd = None

        try:
            self._parse_cfg(nagios_cfg)
        except IOError, ex:
            raise util.InitError("Failed to open Nagios config: %s" % ex)

        try:
            test_skels = self._parse_tests()
        except IOError, ex:
            raise util.InitError("Failed to read Nagios object cache: %s" % ex)

        self._tests = self._fill_templates(templates, test_skels)

    # Provide read-only access to the test list
    def __getitem__(self, key):
        return self._tests[key]

    def __len__(self):
        return len(self._tests)

    def __iter__(self):
        return iter(self._tests)

    def _parse_cfg(self, nagios_cfg):
        """Find the object cache and command file"""

        cfg = open(nagios_cfg)

        for line in cfg:
            line = line.strip()
            if line.startswith("object_cache_file="):
                (var, self._nagios_obj) = line.split("=", 1)
            elif line.startswith("command_file="):
                (var, self._nagios_cmd) = line.split("=", 1)

        cfg.close()

        if self._nagios_obj is None:
            raise util.InitError("Failed to find object_cache_file in %s"
                    % nagios_cfg)
        if self._nagios_cmd is None:
            raise util.InitError("Failed to find command_file in %s"
                    % nagios_cfg)

        # Sanity check that we have access to the command file
        try:
            open(self._nagios_cmd, "a").close()
        except IOError, ex:
            raise util.InitError("Failed to open Nagios command file: %s" % ex)

        log.info("Using Nagios object cache: %s", self._nagios_obj)
        log.info("Using Nagios command file: %s", self._nagios_cmd)

    def _parse_tests(self):
        """Get the list of NagCat services in the object cache"""

        obj = open(self._nagios_obj)

        hosts = {}
        services = []
        current = {}
        ishost = False
        isservice = False
        tests = []

        for line in obj:
            line = line.strip()

            if line == "define host {":
                ishost = True
            elif ishost and line == "}":
                hosts[current['host_name']] = current
                current = {}
                ishost = False
            elif line == "define service {":
                isservice = True
            elif isservice and line == "}":
                services.append(current)
                current = {}
                isservice = False
            elif isservice or ishost:
                split = line.split(None, 1)
                if len(split) == 2:
                    current[split[0]] = split[1]
                else:
                    current[split[0]] = ""

        obj.close()

        for service in services:
            if "_TEST" not in service:
                continue

            test_defaults = {
                    'host': service['host_name'],
                    'addr': hosts[service['host_name']]['address'],
                    'name': service['service_description']}

            test_overrides = {}

            for key in service:
                if len(key) < 2 or key[0] != "_":
                    continue

                # save all vars that start with '_'
                # coil is normally in lower case and Nagios is case insensitive
                test_overrides[key[1:].lower()] = service[key]

            log.debug("Found Nagios service: %s", test_defaults)
            log.debug("Service overrides: %s", test_overrides)
            tests.append((test_defaults, test_overrides))

        return tests

    def _fill_templates(self, templates, skels):
        """Setup tests based on the loaded Nagios config"""

        tests = []

        for test_defaults, test_overrides in skels:
            testconf = templates.get(test_overrides['test'], None)
            if testconf is None:
                raise util.InitError("Test template '%s' not found in config!"
                        % test_overrides['test'])

            # Copy the config so we can add instance specific values
            # such as host, port, etc.
            testconf = testconf.copy()

            for key, val in test_defaults.iteritems():
                testconf.setdefault(key, val)

            for key, val in test_overrides.iteritems():
                testconf[key] = val

            try:
                testobj = test.Test(testconf)
            except util.KnownError, ex:
                raise util.InitError("Error in test %s: %s"
                        % (test_overrides['test'], ex))
            testobj.addReportCallback(self._sendReportInThread,
                    test_defaults['host'], test_defaults['name'])
            tests.append(testobj)

        return tests

    def _sendReportInThread(self, *args, **kwargs):
        reactor.callInThread(self._sendReport, *args, **kwargs)

    def _sendReport(self, report, host_name, service_description):
        # This should be run inside a thread since it may block
        log.debug("Submitting report for %s %s to Nagios",
                host_name, service_description)

        assert report['state'] in util.STATES
        state = util.STATES.index(report['state'])

        msg = "[%s] PROCESS_SERVICE_CHECK_RESULT;%s;%s;%s;%s\n" % (
                int(report['time']), host_name, service_description,
                state, report['text'].replace("\n","\\n") )

        # The | character is special in nagios output :-(
        # It would be nice to escape it instead so reports are correct
        msg = msg.replace('|', '_')

        try:
            cmdfile = open(self._nagios_cmd, "a")
            cmdfile.write(msg)
            cmdfile.close()
        except IOError, ex:
            log.error("Failed to write to Nagios command file: %s", ex)

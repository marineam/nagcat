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

import urllib

from coil.errors import CoilError
from nagcat import errors, log, nagios_api, nagios_objects, test, trend

class NagiosTests(object):
    """Setup tests defined by Nagios and report back"""

    def __init__(self, templates, nagios_cfg, tag=None, url=None):
        """Read given Nagios config file"""

        cfg = nagios_objects.ConfigParser(nagios_cfg,
                ('object_cache_file', 'command_file', 'check_result_path'))
        self._nagios_obj = cfg['object_cache_file']
        spool = nagios_api.spool_path(cfg['check_result_path'], 'nagcat')
        self._nagios_cmd = nagios_api.NagiosCommander(cfg['command_file'], spool)

        log.info("Using Nagios object cache: %s", self._nagios_obj)
        log.info("Using Nagios command file: %s", cfg['command_file'])

        test_skels = self._parse_tests(tag, url)
        self._tests = self._fill_templates(templates, test_skels)

    # Provide read-only access to the test list
    def __getitem__(self, key):
        return self._tests[key]

    def __len__(self):
        return len(self._tests)

    def __iter__(self):
        return iter(self._tests)

    def _parse_tests(self, tag, url):
        """Get the list of NagCat services in the object cache"""

        parser = nagios_objects.ObjectParser(
                self._nagios_obj, ('host', 'service'))
        hosts = {}
        tests = []

        for host in parser['host']:
            hosts[host['host_name']] = host

        for service in parser['service']:
            if "_TEST" not in service:
                continue
            elif tag and service.get("_TAG", None) != tag:
                continue

            test_defaults = {
                    'host': service['host_name'],
                    'addr': hosts[service['host_name']]['address'],
                    'name': service['service_description']}

            if url:
                test_defaults['report_url'] = (
                    "%s/cgi-bin/extinfo.cgi?type=2&host=%s&service=%s" %
                    (url, urllib.quote_plus(service['host_name']),
                    urllib.quote_plus(service['service_description'])))

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
                raise errors.InitError(
                        "Test template '%s' not found in config!"
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
            except (errors.InitError, CoilError), ex:
                raise errors.InitError(
                        "Error in test %s: %s" % (test_overrides['test'], ex))
            except Exception:
                log.error("Unknown error while loading test.")
                log.error("Test config: %s" % repr(testconf))
                log.error(str(errors.Failure()))
                raise errors.InitError(
                        "Error in test %s" % test_overrides['test'])

            testobj.addReportCallback(self._send_report,
                    test_defaults['host'], test_defaults['name'])
            tests.append(testobj)

        return tests

    def _send_report(self, report, host_name, service_description):
        log.debug("Submitting report for %s %s to Nagios",
                host_name, service_description)

        self._nagios_cmd.command(report['time'],
                'PROCESS_SERVICE_CHECK_RESULT', host_name,
                service_description, report['state_id'], report['text'])

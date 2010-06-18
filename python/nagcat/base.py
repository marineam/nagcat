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

"""NagCat initialization and startup"""

from twisted.internet import reactor, task

from nagcat import errors, log, monitor_api
from nagcat import scheduler, test, trend

Nagcat = scheduler.Scheduler

class NagcatDummy(Nagcat):
    """For testing"""

    def build_tests(self, config, tests=()):
        return tests

class NagcatSimple(Nagcat):
    """Run only a single test, do not report to nagios.

    Useful for testing a new test template.
    """

    def _report(self, report):
        log.info("REPORT:\n%s" % report['text'])

    def build_tests(self, config, test_name=None, host=None, port=None):
        config = config.get(test_name, None)
        if not config:
            raise errors.InitError("Test '%s' not found in config file!"
                    % test_name)

        config.setdefault('host', host)
        config.setdefault('port', port)
        config.setdefault('test', test_name)
        config.setdefault('name', test_name)
        config['repeat'] = None # single run

        testobj = test.Test(self, config)
        testobj.addReportCallback(self._report)
        return [testobj]

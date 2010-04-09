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

from __future__ import division

"""Test classes, the real meat.

Tests handle all data processing, error checking, and reporting.
"""

import re
import time

from twisted.internet import defer, reactor
from twisted.python import failure
from coil import struct

from nagcat import errors, filters, log, query, scheduler, trend, util

STATES = ["OK", "WARNING", "CRITICAL", "UNKNOWN"]

TEMPLATE_OK = """%(test)s %(state)s: %(summary)s
Port: %(port)s
Test: %(test)s

Full Output:
%(output)s

Extra Output:
%(extra)s

Documentation:
%(documentation)s

%(url)s
"""

TEMPLATE_BAD = """%(test)s %(state)s: %(summary)s
Port: %(port)s
Test: %(test)s

Error:
%(error)s
%(priority)s
Full Output:
%(output)s

Extra Output:
%(extra)s

Documentation:
%(documentation)s

Investigation:
%(investigation)s

%(url)s
"""


class BaseTest(scheduler.Runnable):
    """Shared base between SimpleTest and Test"""

    def __init__(self, conf):
        scheduler.Runnable.__init__(self, conf)

        self._port = conf.get('port', None)
        # used in return and report
        self._now = time.time()
        # Used by the save filter and report
        self.saved = {}

        # Create the filter objects
        filter_list = conf.get('filters', [])
        self._filters = [filters.Filter(self, x) for x in filter_list]

        # Add final critical and warning tests
        if 'critical' in conf:
            self._filters.append(filters.get_filter(
                self, 'critical', None, conf['critical']))
        if 'warning' in conf:
            self._filters.append(filters.get_filter(
                self, 'warning', None, conf['warning']))

    def _start(self):
        # Subclasses must override this and fire the deferred!
        self.saved.clear()

        deferred = defer.Deferred()

        for filter in self._filters:
            if filter.handle_errors:
                deferred.addBoth(filter.filter)
            else:
                deferred.addCallback(filter.filter)

        return deferred


class ChildError(errors.TestError):
    """This is used to tell Test._report that the error happened in
    a sub-test rather than in the top level Test code.
    """
    pass

class Test(BaseTest):
    """Main test class"""

    def __init__(self, conf):
        BaseTest.__init__(self, conf)

        self._test = conf.get('test', "")
        self._documentation = conf.get('documentation', "")
        self._investigation = conf.get('investigation', "")
        self._priority = conf.get('priority', "")
        self._url = conf.get('url', "")
        self._subtests = {}

        # If self._documentation is a list convert it to a string
        if isinstance(self._documentation, list):
            self._documentation = "\n".join(self._documentation)
        if isinstance(self._investigation, list):
            self._investigation = "\n".join(self._documentation)

        if self._priority:
            self._priority = "Priority: %s\n\n" % self._priority

        if conf['query.type'] == "compound":
            self._compound = True
            conf['query'].expand(recursive=False)
            self._return = conf.get('query.return', None)

            for name, qconf in conf['query'].iteritems():
                if not isinstance(qconf, struct.Struct):
                    continue

                self._addDefaults(qconf)
                self._subtests[name] = query.FilteredQuery(qconf)
                self.addDependency(self._subtests[name])

            if not self._subtests:
                raise errors.ConfigError(conf['query'],
                        "compound query must have a sub-query")
            if self._return or len(self._subtests) > 1:
                if not self._return:
                    raise errors.ConfigError(conf['query'],
                            "return statement is required")

                # Convert $(subquery) to data['subquery']
                self._return = re.sub("\\$\\(([^\\)]+)\\)",
                        lambda m: "data['%s']" % m.group(1), self._return)

                test_values = {'NOW': util.MathString('9999')}
                for name in self._subtests:
                    #XXX this test string isn't fool-proof but will mostly work
                    test_values[name] = util.MathString('9999')

                try:
                    log.trace("Testing expr %r with data=%r" %
                            (self._return, test_values))
                    eval(self._return, {'data': test_values})
                except SyntaxError, ex:
                    raise errors.ConfigError(conf['query'],
                            "Syntax error in return: %s" % ex)
                except KeyError, ex:
                    raise errors.ConfigError(conf['query'],
                            "Unknown sub-query in return: %s" % ex)
        else:
            self._compound = False
            qconf = conf.get('query')
            self._addDefaults(qconf)
            self._subtests['query'] = query.FilteredQuery(qconf)
            self.addDependency(self._subtests['query'])

        self._report_callbacks = []
        trend.addTrend(self, conf)

    def _addDefaults(self, conf):
        """Add default values based on this test to a subtest config"""
        conf.setdefault('host', self.host)
        conf.setdefault('port', self._port)
        conf.setdefault('repeat', str(self.repeat))

        if conf['host'] == self.host:
            conf.setdefault('addr', self.addr)

    def _start(self):
        self._now = time.time()

        # All sub-tests are now complete, process them!
        deferred = BaseTest._start(self)
        deferred.addBoth(self._report)

        try:
            result = self._computeReturn()
        except:
            result = errors.Failure()

        deferred.callback(result)

        return deferred

    def _computeReturn(self):
        if self._compound:
            data = {'NOW': util.MathString(self._now)}
            for name, subtest in self._subtests.iteritems():
                if isinstance(subtest.result, failure.Failure):
                    raise ChildError()
                data[name] = util.MathString(subtest.result)

            log.debug("Evaluating return '%s' with data = %s",
                    self._return, data)

            result = str(eval(self._return, {'data': data}))
        else:
            subtest = self._subtests['query']
            if isinstance(subtest.result, failure.Failure):
                raise ChildError()
            else:
                result = subtest.result

        return result

    def addReportCallback(self, func, *args, **kwargs):
        """The given callback function will be called each time
        this test finishes and has a test to report.

        The first argument will be a dict representing the report.
        """

        assert callable(func)
        self._report_callbacks.append((func, args, kwargs))


    def _report(self, result):
        """Generate a report of the final result, pass that report off
        to all registered report callbacks. (ie nagios reporting)
        """

        def indent(string, prefix="    "):
            ret = ""
            for line in string.splitlines():
                if line.strip():
                    line = prefix+line
                ret += line+'\n'
            return ret

        # Choose what to report at the main result
        if isinstance(result, failure.Failure):
            if isinstance(result.value, ChildError):
                # A child failed, find the worst failure
                level = 0
                failed = None

                for subtest in self._subtests.itervalues():
                    if isinstance(subtest.result, failure.Failure):
                        if isinstance(subtest.result.value, errors.TestError):
                            if subtest.result.value.index > level:
                                level = subtest.result.value.index
                                failed = subtest.result
                        else:
                            # Unknown error, just use it
                            failed = subtest.result
                            break;

                assert failed is not None
            else:
                failed = result

            if (isinstance(failed, errors.Failure) and
                    failed.result is not errors.NO_RESULT):
                output = failed.result
            else:
                output = ""

            if isinstance(failed.value, errors.TestError):
                state = failed.value.state
            else:
                state = "UNKNOWN"

            error = str(failed.value)
            summary = error
        else:
            output = result
            state = "OK"
            error = ""
            summary = result

        # Grab the first 40 characters of the first line
        if summary:
            summary = summary.split('\n', 1)[0][:40]
            if state == "OK" and self.label:
                summary = "%s %s" % (summary, self.label)

        # Fill in the Extra Output area and all valid values
        extra = ""
        results = {}
        for subname, subtest in self._subtests.iteritems():
            subextra = ""
            for savedname, savedval in subtest.saved.iteritems():
                subextra += "    %s:\n" % savedname
                subextra += indent(str(savedval), " "*8)

            if isinstance(subtest.result, failure.Failure):
                results[subname] = ""

                if (isinstance(subtest.result, errors.Failure) and
                        subtest.result.result is not errors.NO_RESULT):
                    subout = str(subtest.result.result)
                else:
                    subout = ""

                if isinstance(subtest.result.value, errors.TestError):
                    suberr = str(subtest.result.value)
                else:
                    suberr = str(subtest.result)
            else:
                results[subname] = subtest.result
                subout = str(subtest.result)
                suberr = ""

            if subout and subout != output:
                subextra += "    Output:\n"
                subextra += indent(subout, " "*8)

            if suberr and suberr != error:
                subextra += "    Error:\n"
                subextra += indent(suberr, " "*8)

            if subextra:
                extra += indent("%s:\n%s" % (subname, subextra))

        assert state in STATES

        if state == "OK":
            text = TEMPLATE_OK
        else:
            text = TEMPLATE_BAD

        report = {
                'test': self._test,
                'state': state,
                'state_id': STATES.index(state),
                'summary': summary,
                'output': output,
                'error': error,
                'extra': extra,
                'host': self.host,
                'addr': self.addr,
                'port': self._port,
                'time': self._now,
                'documentation': self._documentation,
                'investigation': self._investigation,
                'priority': self._priority,
                'url': self._url,
                'results': results,
                }

        text = text % report
        report['text'] = text

        # Don't fire callbacks (which write out to stuff) during shutdown
        if reactor.running:
            for (func, args, kwargs) in self._report_callbacks:
                try:
                    func(report, *args, **kwargs)
                except:
                    log.error("Report callback failed: %s" % failure.Failure())

        return report

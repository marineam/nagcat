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

from nagcat import scheduler, query, filters, util, log

TEMPLATE_OK = """%(test)s %(state)s: %(summary)s
NagCat report for test %(test)s on %(host)s:%(port)s

Full Output:
%(output)s

Extra Output:
%(extra)s

Documentation:
%(documentation)s

%(url)s

%(date)s
"""

TEMPLATE_BAD = """%(test)s %(state)s: %(summary)s
NagCat report for test %(test)s on %(host)s:%(port)s

%(priority)s
Full Output:
%(output)s

Extra Output:
%(extra)s

Error:
%(error)s

Documentation:
%(documentation)s

Investigation:
%(investigation)s

%(url)s

%(date)s
"""


class BaseTest(scheduler.Runnable):
    """Shared base between SimpleTest and Test"""

    def __init__(self, conf):
        assert isinstance(conf, struct.Struct)
        conf.expand(recursive=False)
        host = conf.get('host', None)
        repeat = conf.get('repeat', "1m")
        scheduler.Runnable.__init__(self, repeat, host)

        self._port = conf.get('port', None)

        # Used by the save filter and report
        self.saved = {}

        filter_list = conf.get('filters', [])
        # There is an implicit save filter to aid reporting
        filter_list.append("save")

        self._filters = [filters.Filter(self, x) for x in filter_list]

    def _createDeferred(self):
        """Create a Deferred object, should be returned by _start()"""
        deferred = defer.Deferred()

        for filter in self._filters:
            deferred.addCallback(filter.filter)

        return deferred

class SimpleTest(BaseTest):
    """Used only as sub-tests"""

    def __init__(self, conf):
        """conf is a coil config defining the test"""

        BaseTest.__init__(self, conf)

        self._query = query.addQuery(conf)
        self.addDependency(self._query)

    def _start(self):
        self.saved.clear()
        deferred = self._createDeferred()
        deferred.callback(self._query.result)
        return deferred


class ChildError(Exception):
    """This is used to tell Test._report that the error happened in
    a sub-test rather than in the top level Test code.
    """
    pass

class Test(BaseTest):
    """Main test class"""

    def __init__(self, conf):
        BaseTest.__init__(self, conf)

        self._test = conf.get('test', None)
        self._critical = conf.get('critical', None)
        self._warning = conf.get('warning', None)
        self._documentation = conf.get('documentation', "")
        self._investigation = conf.get('investigation', "")
        self._priority = conf.get('priority', "")
        self._url = conf.get('url', "")
        self._subtests = {}

        # If self._documentation is a list convert it to a string
        if isinstance(self._documentation, list):
            doc = ""
            for line in self._documentation:
                doc = "%s%s\n" % (doc, line)
            self._documentation = doc.rstrip()

        if isinstance(self._investigation, list):
            inv = ""
            for line in self._investigation:
                inv = "%s%s\n" % (inv, line)
            self._investigation = inv.rstrip()

        if self._priority:
            self._priority = "Priority: %s\n" % self._priority

        if conf['query.type'] == "compound":
            self._compound = True
            conf.expand(recursive=False)
            self._return = conf.get('query.return', None)

            if self._return:
                # Convert $(subquery) to data['subquery']
                self._return = re.sub("\\$\\(([^\\)]+)\\)",
                        lambda m: "data['%s']" % m.group(1),
                        self._return)

            for name, qconf in conf['query'].iteritems():
                if not isinstance(qconf, struct.Struct):
                    continue

                self._addDefaults(qconf)
                self._subtests[name] = SimpleTest(qconf)
                self.addDependency(self._subtests[name])
        else:
            self._compound = False
            self._addDefaults(conf.get('query'))
            self._subtests['query'] = SimpleTest(conf.get('query'))
            self.addDependency(self._subtests['query'])

        self._report_callbacks = []

    def _addDefaults(self, conf):
        """Add default values based on this test to a subtest config"""
        conf.setdefault('host', self.host)
        conf.setdefault('port', self._port)
        conf.setdefault('repeat', str(self.repeat))

    def _start(self):
        self.saved.clear()

        # All sub-tests are now complete, if this was a compound query
        # compute return will put the pieces together.
        try:
            result = self._computeReturn()
        except:
            result = failure.Failure()

        deferred = self._createDeferred()
        deferred.callback(result)
        deferred.addCallback(self._checkAllThresholds)
        deferred.addBoth(self._report)

        return deferred

    def _computeReturn(self):
        # Time the subtests completed, used here and in _report()
        self._now = time.time()

        if self._compound:
            data = {'NOW': util.MathString(time.time())}
            for name, subtest in self._subtests.iteritems():
                if isinstance(subtest.result, failure.Failure):
                    raise ChildError()
                data[name] = util.MathString(subtest.result)

            log.debug("Evaluating return '%s' with data = %s"
                        % (self._return, data))

            try:
                result = str(eval(self._return, {'data': data}))
            except SyntaxError, ex:
                raise util.KnownError(
                        "Syntax error in return!", error=ex)
            except KeyError, ex:
                raise util.KnownError(
                        "Unknown sub-query in return!", error=ex)

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

    def _checkThreshold(self, result, threshold, state):
        """Raise an exception if the result value matches the threshold.

        This is only used by _report().
        """

        ops = ('>','<','=','==','>=','<=','<>','!=','=~','!~')

        match = re.match("([<>=!~]{1,2})\s*(\S+.*)", threshold)
        if not match:
            raise util.KnownError("Invalid %s test: %s"
                    % (state.lower(), threshold), result)

        thresh_op = match.group(1)
        thresh_val = match.group(2)

        if thresh_op not in ops:
            raise util.KnownError("Invalid %s test operator: %s"
                    % (state.lower(), thresh_op), result)

        if '~' in thresh_op:
            # Check for a valid regular expression
            try:
                regex = re.compile(thresh_val)
            except re.error, ex:
                raise util.KnownError("Invalid %s test regex: '%s'"
                        % (state.lower(), thresh_val), result, error=ex)

        if thresh_op == '=~':
            if re.search(regex, result, re.MULTILINE):
                raise util.KnownError(threshold, result, state)
        elif thresh_op == '!~':
            if not re.search(regex, result, re.MULTILINE):
                raise util.KnownError(threshold, result, state)
        else:
            # not a regular expression, let MathString do its magic.
            thresh_val = util.MathString(thresh_val)
            result = util.MathString(result)

            # Convert non-python operators
            if thresh_op == '=':
                thresh_op = '=='
            if thresh_op == '<>':
                thresh_op = '!='

            if eval("a %s b" % thresh_op, {'a':result, 'b':thresh_val}):
                raise util.KnownError(threshold, result, state)

    def _checkAllThresholds(self, result):
        if self._critical:
            self._checkThreshold(result, self._critical, "CRITICAL")
        if self._warning:
            self._checkThreshold(result, self._warning, "WARNING")
        return result

    def _report(self, result):
        """Generate a report of the final result, pass that report off
        to all registered report callbacks. (ie nagios reporting)
        """

        def getstate(test, result):
            # Pull values and error messages out of any failures
            if not isinstance(result, failure.Failure):
                output = str(result)
                error = ""
                state = "OK"
                summary = output
            # warning/critical tests result in a KnownError as well as 
            # other issues where we can give a decent error message
            elif (isinstance(result.value, util.KnownError)):
                output = str(result.value.result)
                error = str(result.value.error)
                state = result.value.state
                summary = str(result.value)
            else:
                output = ""
                error = str(result.value)
                state = "UNKNOWN"
                summary = error

            return (summary, output, error, state)

        # Don't generate reports during shut down
        if not reactor.running:
            return

        if (isinstance(result, failure.Failure) and
                isinstance(result.value, ChildError)):
            # A child failed, find the worst failure
            output = ""
            error = ""
            state = "OK"
            summary = "Something failed but I don't know what."

            for subtest in self._subtests.itervalues():
                subsum, subout, suberr, substat = \
                        getstate(subtest, subtest.result)
                if util.STATES.index(substat) > util.STATES.index(state):
                    state = substat
                    summary = subsum
                    output = subout
                    error = suberr
        elif isinstance(result, failure.Failure):
            # Failed in return or threshold
            summary, output, error, state = getstate(self, result)
        else:
            # All is well!
            output = str(result)
            summary = output
            state = "OK"
            error = ""

        # Grab the first 40 characters of the first line
        if summary:
            summary = summary.splitlines()[0][:40]

        # Fill in the Extra Output area
        for subname, subtest in self._subtests.iteritems():
            for savedname, savedval in subtest.saved.iteritems():
                if savedname is None:
                    savedname = subname
                self.saved.setdefault(savedname, savedval)

        extra = ""
        for savedname, savedval in self.saved.iteritems():
            # Skip the default extra output for this top level test,
            # it likely does not include anything new
            if savedname is not None and savedval != output:
                extra += "%s: %s\n" % (savedname, savedval)

        assert state in util.STATES
        if state == "OK":
            text = TEMPLATE_OK
        else:
            text = TEMPLATE_BAD

        report = {
                'test': self._test,
                'state': state,
                'summary': summary,
                'output': output,
                'error': error,
                'extra': extra,
                'host': self.host,
                #'addr': self._addr,
                'port': self._port,
                'date': time.ctime(self._now),
                'time': self._now,
                'documentation': self._documentation,
                'investigation': self._investigation,
                'priority': self._priority,
                'url': self._url,
                }

        text = text % report
        report['text'] = text

        for (func, args, kwargs) in self._report_callbacks:
            func(report, *args, **kwargs)

        return report

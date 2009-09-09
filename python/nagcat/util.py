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

"""Exceptions and configuration bits that are used everywhere"""

import re
import os
import sys
import grp
import pwd
import resource

from nagcat import log

class IntervalError(Exception):
    """Error creating time interval object"""

class Interval(object):
    """Store the duration of time interval.

    A if initialized with None or '0 seconds' this the object
    will evaluate to False in boolean contexts.
    """
    # TODO: support absolute times

    def __init__(self, value):
        if not value:
            # Default to no repeat
            self.seconds = 0.0
            return

        match = re.match("^\s*(\d+(\.\d+)?)\s*"
                "(s|sec|seconds?|m|min|minutes?|h|hours?|d|days?)\s*$",
                str(value), re.IGNORECASE)
        if not match:
            raise IntervalError("Invalid time interval '%s'" % value)

        if match.group(3)[0].lower() == 's':
            self.seconds = float(match.group(1))
        elif match.group(3)[0].lower() == 'm':
            self.seconds = float(match.group(1)) * 60
        elif match.group(3)[0].lower() == 'h':
            self.seconds = float(match.group(1)) * 3600
        elif match.group(3)[0].lower() == 'd':
            self.seconds = float(match.group(1)) * 86400
        else:
            assert(0)

    def __str__(self):
        return "%s seconds" % self.seconds

    def __float__(self):
        return self.seconds

    def __int__(self):
        return int(self.seconds)

    def __nonzero__(self):
        return bool(self.seconds)

    def __eq__(self, other):
        if (isinstance(other, self.__class__) and
                self.seconds == other.seconds):
            return True
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

class MathError(Exception):
    """Attempted math on a non-numeric value"""

class MathString(str):
    """A string that supports numeric operations.

    This allows evaluations done on test results to not have to worry
    about casting between string and number types by behaving like a
    number for for all standard math operations. Of course if the user
    wants to run a stringified math operation such as "foo"+"bar" they
    will have to cast using str() first. But in the case of the +
    operator "%s" % foo style syntax is usually much better anyway.

    The following operators are computed as a number:

        + - * / // % divmod() pow() ** < <= >= >

    Use of these operators on any non-numeric value will raise a MathError

    The == and != operators will do a numeric comparison if the two
    values happen to be numbers, otherwise it will compare them as
    strings.
    """

    def __digify_args(*args):
        """Covert all arguments to a number"""

        numbers = []

        for arg in args:
            if isinstance(arg, MathString):
                if '.' in arg:
                    numtype = float
                else:
                    numtype = int

                try:
                    arg = numtype(arg)
                except ValueError:
                    raise MathError("The value '%s' is not a number" % str(arg))

            numbers.append(arg)

        return numbers

    def __float__(self):
        return float(str(self))

    def __int__(self):
        try:
            return int(str(self))
        except ValueError:
            return int(float(self))

    def __long__(self):
        try:
            return long(str(self))
        except ValueError:
            return long(float(self))

    def __add__(self, other):
        nself, nother = self.__digify_args(other)
        return nself + nother

    def __radd__(self, other):
        nself, nother = self.__digify_args(other)
        return nother + nself

    def __sub__(self, other):
        nself, nother = self.__digify_args(other)
        return nself - nother

    def __rsub__(self, other):
        nself, nother = self.__digify_args(other)
        return nother - nself

    def __mul__(self, other):
        nself, nother = self.__digify_args(other)
        return nself * nother

    def __rmul__(self, other):
        nself, nother = self.__digify_args(other)
        return nother * nself

    def __truediv__(self, other):
        nself, nother = self.__digify_args(other)
        return nself / nother

    def __rtruediv__(self, other):
        nself, nother = self.__digify_args(other)
        return nother / nself

    def __floordiv__(self, other):
        nself, nother = self.__digify_args(other)
        return nself // nother

    def __rfloordiv__(self, other):
        nself, nother = self.__digify_args(other)
        return nother // nself

    def __mod__(self, other):
        nself, nother = self.__digify_args(other)
        return nself % nother

    def __rmod__(self, other):
        nself, nother = self.__digify_args(other)
        return nother % nself

    def __divmod__(self, other):
        nself, nother = self.__digify_args(other)
        return divmod(nself, nother)

    def __rdivmod__(self, other):
        nself, nother = self.__digify_args(other)
        return divmod(nother, nself)

    def __pow__(self, other, mod=None):
        if mod is None:
            nself, nother = self.__digify_args(other)
            return nself ** nother
        else:
            nself, nother, nmod = self.__digify_args(other, mod)
            return pow(nself, nother, nmod)

    def __rpow__(self, other):
        nself, nother = self.__digify_args(other)
        return nother ** nself

    def __neg__(self):
        nself, = self.__digify_args()
        return -nself

    def __abs__(self):
        nself, = self.__digify_args()
        return abs(nself)

    def __lt__(self, other):
        nself, nother = self.__digify_args(other)
        return nself < nother

    def __le__(self, other):
        nself, nother = self.__digify_args(other)
        return nself <= nother

    def __gt__(self, other):
        nself, nother = self.__digify_args(other)
        return nself > nother

    def __ge__(self, other):
        nself, nother = self.__digify_args(other)
        return nself >= nother

    def __eq__(self, other):
        try:
            nself, nother = self.__digify_args(other)
            ret = nself == nother
        except MathError:
            ret = str.__eq__(self, other)

        return ret

    def __ne__(self, other):
        return not self.__eq__(other)


def setup(user=None, group=None, file_limit=None):
    """Set the processes user, group, and file limits"""

    if file_limit:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (file_limit, file_limit))
        except ValueError, ex:
            log.error("Failed to set limit on open files: %s" % ex)
            sys.exit(1)

    if group:
        if not group.isdigit():
            try:
                group = grp.getgrnam(group)[2]
            except KeyError:
                log.error("Unknown group '%s'" % group)
                sys.exit(1)
        else:
            group = int(group)

        try:
            os.setregid(group, group)
        except OSError, ex:
            log.error("Failed to set gid: %s" % ex)
            sys.exit(1)

    if user:
        if not user.isdigit():
            try:
                user = pwd.getpwnam(user)[2]
            except KeyError:
                log.error("Unknown user '%s'" % user)
                sys.exit(1)
        else:
            user = int(user)

        try:
            os.setreuid(user, user)
        except OSError, ex:
            log.error("Failed to set uid: %s" % ex)
            sys.exit(1)


def daemonize(pid_file):
    """Background the current process"""

    log.debug("daemonizing process")

    try:
        # A trivial check to see if we are already running
        pidfd = open(pid_file)
        pid = int(pidfd.readline().strip())
        pidfd.close()
        os.kill(pid, 0)
    except (IOError, OSError):
        pass # Assume all is well if the test raised no errors
    else:
        log.error("PID file exits and process %s is running!" % pid)
        sys.exit(1)

    try:
        null = os.open("/dev/null", os.O_RDWR)
    except OSError, ex:
        log.error("Failed to open /dev/null!")
        log.error("Error: %s" % (ex,))
        sys.exit(1)

    try:
        pidfd = open(pid_file, 'w')
    except IOError, ex:
        log.error("Failed to open PID file %s" % pid_file)
        log.error("Error: %s" % (ex,))
        sys.exit(1)

    if os.fork() > 0:
        os._exit(0)

    os.chdir("/")
    os.setsid()
    os.dup2(null, 0)
    os.dup2(null, 1)
    os.dup2(null, 2)

    if os.fork() > 0:
        os._exit(0)

    pidfd.write("%s\n" % os.getpid())
    pidfd.close()


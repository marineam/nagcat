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

import os
import sys
import pwd
import grp
import resource
from UserDict import DictMixin
from optparse import OptionParser

from twisted.internet import reactor
import coil

from nagcat import errors, log, nagios, scheduler, test, trend

def simpleReport(report):
    log.info("REPORT:\n%s" % report['text'])

def simple(options, config):
    """Run only a single test, do not report to nagios.

    Useful for testing a new test template.
    """

    config = config.get(options.test, None)
    if config is None:
        raise errors.InitError("Test '%s' not found in config file!"
                % options.test)

    config.setdefault('host', options.host)
    config.setdefault('port', options.port)
    config.setdefault('test', options.test)
    config.setdefault('name', options.test)
    config['repeat'] = None # single run

    testobj = test.Test(config)
    testobj.addReportCallback(simpleReport)

    return [testobj]

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

        if os.path.isdir('/proc/%s' % pid):
            log.error("PID file exits and process %s is running!" % pid)
            sys.exit(1)
    except:
        # Assume all is well if the test fails
        pass

    try:
        pidfd = open(pid_file, 'w')
    except IOError, ex:
        log.error("Failed to open PID file %s" % pid_file)
        sys.exit(1)

    if os.fork() > 0:
        os._exit(0)

    os.chdir("/")
    os.setsid()

    if os.fork() > 0:
        os._exit(0)

    pidfd.write("%s\n" % os.getpid())
    pidfd.close()


def parse_options():
    """Parse program options in sys.argv"""

    parser = OptionParser()

    parser.add_option("-c", "--config", dest="config",
            help="coil config file with test templates")
    parser.add_option("-v", "--loglevel", dest="loglevel",
            default="INFO", help="one of: ERROR WARN INFO DEBUG")
    parser.add_option("-l", "--logfile", dest="logfile",
            help="log file, automatically rotated")
    parser.add_option("-p", "--pidfile", dest="pidfile",
            help="pid file (daemon mode only)")
    parser.add_option("-d", "--daemon", dest="daemon",
            action="store_true", default=False,
            help="run as a daemon")
    parser.add_option("-u", "--user", dest="user",
            help="run as the given user")
    parser.add_option("-g", "--group", dest="group",
            help="run as the given group")
    parser.add_option("-f", "--file-limit", dest="file_limit", type="int",
            help="set the limit on number of open files")
    parser.add_option("-r", "--rradir", dest="rradir",
            help="directory used to store rrdtool archives")
    parser.add_option("-t", "--test", dest="test",
            help="only run a single test")
    parser.add_option("-H", "--host", dest="host",
            help="host to use when only running one test")
    parser.add_option("-P", "--port", dest="port", type="int",
            help="port to use when only running one test")
    parser.add_option("-n", "--nagios", dest="nagios",
            help="path to nagios.cfg, enables Nagios support")
    parser.add_option("", "--profile-init", dest="profile_init",
            action="store_true", default=False,
            help="run profiler during startup")
    parser.add_option("", "--profile-run", dest="profile_run",
            action="store_true", default=False,
            help="run profiler during normal operation")
    parser.add_option("", "--profile-all", dest="profile_all",
            action="store_true", default=False,
            help="alias for --profile-init --profile-run")

    (options, args) = parser.parse_args()

    err = []
    if not options.config:
        err.append("--config is required")

    if options.daemon and (not options.pidfile or not options.logfile):
        err.append("--logfile and --pidfile are required with --daemon")

    if options.daemon and options.test:
        err.append("--test cannot be used with --daemon")

    if options.test and (not options.host or not options.port):
        err.append("--host and --port is required with --test")

    if options.loglevel not in log.LEVELS:
        err.append("invalid log level '%s'" % options.loglevel)
        err.append("must be one of: %s" % " ".join(log.LEVELS))

    if options.profile_all:
        options.profile_init = True
        options.profile_run = True

    if err:
        parser.error("\n".join(err))

    return options


def init(options):
    """Prepare to start up NagCat"""

    # Sanity check, make sure we are using >= coil-0.3.0
    if (not issubclass(coil.struct.Struct, DictMixin)):
        raise Exception("Coil >= 0.3.0 is required!")

    log.init(options.logfile, options.loglevel)
    config = coil.parse_file(options.config, expand=False)

    try:
        if options.rradir:
            trend.init(options.rradir)

        if options.test:
            tests = simple(options, config)
        elif options.nagios:
            tests = nagios.NagiosTests(config, options.nagios)
        else:
            raise Exception("Normal mode without nagios is unimplemented")

        sch = scheduler.Scheduler()
        for testobj in tests:
            sch.register(testobj)

        sch.prepare()
        reactor.callWhenRunning(sch.start)
    except (errors.InitError, coil.errors.CoilError), ex:
        log.error(str(ex))
        sys.exit(1)

    # Set uid/gid/file_limit
    setup(options.user, options.group, options.file_limit)

    # daemonize and redirect stdio to log
    if options.daemon:
        daemonize(options.pidfile)
        log.init_stdio(close=True)
    else:
        log.init_stdio()

def main():
    """Start up NagCat, profiling things as requested"""

    options = parse_options()

    if options.profile_init or options.profile_run:
        import cProfile
        profiler = cProfile.Profile()

    if options.profile_init:
        profiler.runcall(init, options)
    else:
        init(options)

    if options.profile_run:
        profiler.runcall(reactor.run)
    else:
        reactor.run()

    if options.profile_init or options.profile_run:
        import pstats
        stats = pstats.Stats(profiler)
        stats.strip_dirs()
        stats.sort_stats('time', 'cumulative')
        #stats.sort_stats('calls')
        stats.print_stats(30)
        stats.print_callers(30)

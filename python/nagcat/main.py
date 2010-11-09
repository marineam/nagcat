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
from optparse import OptionParser

from twisted.internet import reactor
import coil

from nagcat import errors, log, nagios, plugin, query, simple, util

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
            help="pid file")
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
    parser.add_option("-R", "--rrdcache",
            default=os.environ.get('RRDCACHED_ADDRESS', None),
            help="path to unix socket rrdcache is listening on")
    parser.add_option("-s", "--status-port", dest="status_port", type="int",
            help="enable the HTTP status port")
    parser.add_option("-V", "--verify", dest="verify",
            action="store_true", default=False,
            help="verify the config but don't start")
    parser.add_option("-t", "--test", dest="test",
            help="only run a single test")
    parser.add_option("-H", "--host", dest="host",
            help="host to use when only running one test")
    parser.add_option("-P", "--port", dest="port", type="int",
            help="port to use when only running one test")
    parser.add_option("-n", "--nagios", dest="nagios",
            help="path to nagios.cfg, enables Nagios support")
    parser.add_option("-T", "--tag", dest="tag",
            help="only load nagios tests with a specific tag")
    parser.add_option("-C", "--core-dumps",
            help="set cwd to the given directory and enable core dumps")
    parser.add_option("--disable-snmp-bulk", action="store_true",
            help="disable the use of SNMPv2's GETBULK command")
    parser.add_option("", "--profile-init", dest="profile_init",
            action="store_true", default=False,
            help="run profiler during startup")
    parser.add_option("", "--profile-run", dest="profile_run",
            action="store_true", default=False,
            help="run profiler during normal operation")
    parser.add_option("", "--profile-all", dest="profile_all",
            action="store_true", default=False,
            help="alias for --profile-init --profile-run")
    parser.add_option("", "--profile-dump", dest="profile_dump",
            help="dump profiler data rather than displaying it")

    (options, args) = parser.parse_args()

    err = []
    if not options.config:
        err.append("--config is required")

    if options.daemon and (not options.pidfile or not options.logfile):
        err.append("--logfile and --pidfile are required with --daemon")

    if (not (options.nagios or options.test) or
            (options.nagios and options.test)):
        err.append("either --test or --nagios is required")

    if options.pidfile and options.verify:
        err.append("--verify shouldn't be used with --pidfile")

    if options.daemon and options.verify:
        err.append("--verify cannot be used with --daemon")

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

def stop(result):
    reactor.stop()
    return result

def start(nagcat):
    d = nagcat.start()
    d.addBoth(stop)

def init_plugins(options):
    """Pass any parameters to plugins."""
    # Yes, this could be done in a more generic way with plugins providing
    # a specific interface that provides both the plugin's options and
    # a function to process those options. For now this is sufficient.

    snmp = plugin.search(query.IQuery, "snmp")
    snmp.use_bulk(not options.disable_snmp_bulk)

def init(options):
    """Prepare to start up NagCat"""

    # Set uid/gid/file_limit
    util.setup(options.user, options.group,
               options.file_limit,
               options.core_dumps)

    # Write out the pid to make the verify script happy
    if options.pidfile:
        util.write_pid(options.pidfile)

    log.init(options.logfile, options.loglevel)
    config = coil.parse_file(options.config, expand=False)

    init_plugins(options)

    try:
        if options.test:
            nagcat = simple.NagcatSimple(config,
                    rradir=options.rradir,
                    rrdcache=options.rrdcache,
                    monitor_port=options.status_port,
                    test_name=options.test,
                    host=options.host, port=options.port)
        else:
            nagcat = nagios.NagcatNagios(config,
                    rradir=options.rradir,
                    rrdcache=options.rrdcache,
                    monitor_port=options.status_port,
                    nagios_cfg=options.nagios, tag=options.tag)
    except (errors.InitError, coil.errors.CoilError), ex:
        log.error(str(ex))
        sys.exit(1)

    reactor.callWhenRunning(start, nagcat)

    if options.verify:
        sys.exit(0)

    if options.core_dumps:
        cwd = options.core_dumps
    else:
        cwd = "/"

    if options.daemon:
        util.daemonize(options.pidfile, cwd)
    else:
        os.chdir(cwd)

    # redirect stdio to log
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
        if options.profile_dump:
            log.info("Dumping profiler data to %s" % options.profile_dump)
            profiler.dump_stats(options.profile_dump)
        else:
            log.info("Generating profiler stats...")
            import pstats
            stats = pstats.Stats(profiler)
            stats.strip_dirs()
            stats.sort_stats('time', 'cumulative')
            stats.print_stats(40)

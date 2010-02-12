# Copyright 2010 ITA Software, Inc.
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

import re
from twisted.trial import unittest
from nagcat import errors, notify
import coil

ENVIRONMENT_HOST = {
    # Host Macros
    'NAGIOS_HOSTNAME':              "localhost",
    'NAGIOS_HOSTDISPLAYNAME':       "localhost",
    'NAGIOS_HOSTALIAS':             "localhost",
    'NAGIOS_HOSTADDRESS':           "127.0.0.1",
    'NAGIOS_HOSTSTATE':             "UP",
    'NAGIOS_HOSTSTATEID':           "0",
    'NAGIOS_LASTHOSTSTATE':         "UP",
    'NAGIOS_LASTHOSTSTATEID':       "0",
    'NAGIOS_HOSTSTATETYPE':         "HARD",
    'NAGIOS_HOSTATTEMPT':           "1",
    'NAGIOS_MAXHOSTATTEMPTS':       "3",
    'NAGIOS_HOSTEVENTID':           "0",
    'NAGIOS_LASTHOSTEVENTID':       "0",
    'NAGIOS_HOSTPROBLEMID':         "0",
    'NAGIOS_LASTHOSTPROBLEMID':     "0",
    'NAGIOS_HOSTLATENCY':           "0.123",
    'NAGIOS_HOSTEXECUTIONTIME':     "4.012",
    'NAGIOS_HOSTDURATION':          "35d 15h 31m 49s",
    'NAGIOS_HOSTDURATIONSEC':       "3079909",
    'NAGIOS_HOSTDOWNTIME':          "0",
    'NAGIOS_HOSTPERCENTCHANGE':     "0.0",
    'NAGIOS_HOSTGROUPNAMES':        "a_group,b_group",
    'NAGIOS_LASTHOSTCHECK':         "1260009929",
    'NAGIOS_LASTHOSTSTATECHANGE':   "1256929950",
    'NAGIOS_LASTHOSTUP':            "1260009939",
    'NAGIOS_LASTHOSTDOWN':          "0",
    'NAGIOS_LASTHOSTUNREACHABLE':   "0",
    'NAGIOS_HOSTOUTPUT':            "PING OK - Packet loss = 0%, RTA = 2.00 ms",
    'NAGIOS_LONGHOSTOUTPUT':        "",
    'NAGIOS_HOSTPERFDATA':          "rta=10.778000ms;3000.000000;5000.000000;0.000000 pl=0%;80;100;0",
    'NAGIOS_HOSTCHECKCOMMAND':      "check_host_alive",
    'NAGIOS_HOSTACTIONURL':         "",
    'NAGIOS_HOSTNOTESURL':          "",
    'NAGIOS_HOSTNOTES':             "",
    'NAGIOS_TOTALHOSTSERVICES':         "39",
    'NAGIOS_TOTALHOSTSERVICESOK':       "38",
    'NAGIOS_TOTALHOSTSERVICESWARNING':  "0",
    'NAGIOS_TOTALHOSTSERVICESCRITICAL': "1",
    'NAGIOS_TOTALHOSTSERVICESUNKNOWN':  "0",

    # Host Group Macros
    'NAGIOS_HOSTGROUPNAME':         "a_group",
    'NAGIOS_HOSTGROUPALIAS':        "A Group",
    'NAGIOS_HOSTGROUPMEMBERS':      "localhost",
    'NAGIOS_HOSTGROUPNOTES':        "",
    'NAGIOS_HOSTGROUPNOTESURL':     "",
    'NAGIOS_HOSTGROUPACTIONURL':    "",

    # Contact Macros
    'NAGIOS_CONTACTNAME':           "root",
    'NAGIOS_CONTACTALIAS':          "Mr. Big",
    'NAGIOS_CONTACTEMAIL':          "root@localhost",
    'NAGIOS_CONTACTPAGER':          "pager@localhost",
    'NAGIOS_CONTACTGROUPNAMES':     "admins,managers",
    # The address fields could be anything...
    #'NAGIOS_CONTACTADDRESS0':       "",

    # Contact Group Macros
    'NAGIOS_CONTACTGROUPNAME':      "admins",
    'NAGIOS_CONTACTGROUPALIAS':     "Admins",
    'NAGIOS_CONTACTGROUPMEMBERS':   "root,luser",

    # Summary Macros (NAGIOS_TOTAL*) are not always available
    # so they are not included here...

    # Notification Macros
    'NAGIOS_NOTIFICATIONTYPE':          "PROBLEM",
    'NAGIOS_NOTIFICATIONRECIPIENTS':    "root",
    'NAGIOS_NOTIFICATIONISESCALATED':   "0",
    'NAGIOS_NOTIFICATIONAUTHOR':        "",
    'NAGIOS_NOTIFICATIONAUTHORNAME':    "",
    'NAGIOS_NOTIFICATIONAUTHORALIAS':   "",
    'NAGIOS_NOTIFICATIONCOMMENT':       "",
    'NAGIOS_NOTIFICATIONNUMBER':        "1",
    'NAGIOS_HOSTNOTIFICATIONNUMBER':    "0",
    'NAGIOS_HOSTNOTIFICATIONID':        "0",
    'NAGIOS_SERVICENOTIFICATIONNUMBER': "1",
    'NAGIOS_SERVICENOTIFICATIONID':     "409161",

    # Date/Time Macros
    'NAGIOS_LONGDATETIME':          "Sun Dec 6 04:25:32 EST 2009",
    'NAGIOS_SHORTDATETIME':         "12-06-2009 04:25:33",
    'NAGIOS_DATE':                  "12-06-2009",
    'NAGIOS_TIME':                  "04:25:34",
    'NAGIOS_TIMET':                 "1260091534",

    # File Macros:
    'NAGIOS_MAINCONFIGFILE':        "/path/to/nagios.cfg",
    'NAGIOS_STATUSDATAFILE':        "/path/to/status.dat",
    'NAGIOS_RETENTIONDATAFILE':     "/path/to/retention.dat",
    'NAGIOS_OBJECTCACHEFILE':       "/path/to/objects.cache",
    'NAGIOS_TEMPFILE':              "/path/to/nagios.tmp",
    'NAGIOS_TEMPPATH':              "/tmp",
    'NAGIOS_LOGFILE':               "/path/to/nagios.log",
    'NAGIOS_RESOURCEFILE':          "/path/to/resource.cfg",
    'NAGIOS_COMMANDFILE':           "/path/to/nagios.cmd",

    # Misc Macros:
    'NAGIOS_PROCESSSTARTTIME':      "1259966149",
    'NAGIOS_EVENTSTARTTIME':        "1259966149",
    'NAGIOS_ADMINEMAIL':            "root@localhost",
    'NAGIOS_ADMINPAGER':            "pager@localhost",
    # These are available but could be anything...
    #'NAGIOS_ARG0':                  "",
    #'NAGIOS_USER0':                 "",
}

ENVIRONMENT_SERVICE = {
    # Service Macros
    'NAGIOS_SERVICEDESC':           "PING",
    'NAGIOS_SERVICEDISPLAYNAME':    "PING",
    'NAGIOS_SERVICESTATE':          "CRITICAL",
    'NAGIOS_SERVICESTATEID':        "2",
    'NAGIOS_LASTSERVICESTATE':      "CRITICAL",
    'NAGIOS_LASTSERVICESTATEID':    "2",
    'NAGIOS_SERVICESTATETYPE':      "HARD",
    'NAGIOS_SERVICEATTEMPT':        "3",
    'NAGIOS_MAXSERVICEATTEMPTS':    "3",
    'NAGIOS_SERVICEISVOLATILE':     "0",
    'NAGIOS_SERVICEEVENTID':        "56460",
    'NAGIOS_LASTSERVICEEVENTID':    "56405",
    'NAGIOS_SERVICEPROBLEMID':      "28201",
    'NAGIOS_LASTSERVICEPROBLEMID':  "0",
    'NAGIOS_SERVICELATENCY':        "0.357",
    'NAGIOS_SERVICEEXECUTIONTIME':  "0.000",
    'NAGIOS_SERVICEDURATION':       "0d 0h 0m 17s",
    'NAGIOS_SERVICEDURATIONSEC':    "17",
    'NAGIOS_SERVICEDOWNTIME':       "0",
    'NAGIOS_SERVICEPERCENTCHANGE':  "12.37",
    'NAGIOS_SERVICEGROUPNAMES':     "z_gorup,y_group",
    'NAGIOS_LASTSERVICECHECK':          "1260146052",
    'NAGIOS_LASTSERVICESTATECHANGE':    "1260146112",
    'NAGIOS_LASTSERVICEOK':             "1260146052",
    'NAGIOS_LASTSERVICEWARNING':        "1260091455",
    'NAGIOS_LASTSERVIVECRITICAL':       "1260146112",
    'NAGIOS_LASTSERVICEUNKNOWN':        "1257999616",
    'NAGIOS_SERVICEOUTPUT':         "PING CRITICAL - Packet loss = 60%, RTA = 0.38 ms",
    'NAGIOS_LONGSERVICEOUTPUT':     "Long Output\\nWith\\nextra lines",
    'NAGIOS_SERVICEPERFDATA':       "",
    'NAGIOS_SERVICECHECKCOMMAND':   "check_freshness",
    'NAGIOS_SERVICEACTIONURL':      "",
    'NAGIOS_SERVICENOTESURL':       "",
    'NAGIOS_SERVICENOTES':          "",

    # Service Group Macros
    'NAGIOS_SERVICEGROUPNAME':      "z_group",
    'NAGIOS_SERVICEGROUPALIAS':     "Z Group",
    'NAGIOS_SERVICEGROUPMEMBERS':   "localhost,PING,otherhost,PING",
    'NAGIOS_SERVICEGROUPNOTESURL':  "",
    'NAGIOS_SERVICEGROUPNOTES':     "",
}
ENVIRONMENT_SERVICE.update(ENVIRONMENT_HOST)

class MacrosTestCase(unittest.TestCase):

    def setUp(self):
        self.macros = notify.Macros(ENVIRONMENT_SERVICE)

    def testPrefix(self):
        for key in self.macros:
            self.failIf(key.startswith("NAGIOS_"))

    def testNewlines(self):
        for key, value in self.macros.iteritems():
            if key == "LONGSERVICEOUTPUT":
                self.assert_(len(value.splitlines()) > 1)
            else:
                self.assert_(not value or len(value.splitlines()) == 1)

    def testMissing(self):
        self.assertRaises(notify.MissingMacro,
                lambda: self.macros['DOESNOTEXIST'])

class NotificationTest(unittest.TestCase):

    def setUp(self):
        self.macros = {
                'host': notify.Macros(ENVIRONMENT_HOST),
                'service': notify.Macros(ENVIRONMENT_SERVICE)}
        self.config = coil.parse(notify.DEFAULT_CONFIG)

    def testSubject(self):
        for t in ('host', 'service'):
            obj = notify.Notification(t, self.macros[t], self.config)
            self.assert_(obj.subject())

    def testBody(self):
        for t in ('host', 'service'):
            obj = notify.Notification(t, self.macros[t], self.config)
            long = obj.body()
            self.assert_(long)
            self.failIf(re.search('{\w+}', long))
            obj.format = "short"
            short = obj.body()
            self.assert_(short)
            self.failIf(re.search('{\w+}', short))
            self.assert_(len(short) < len(long))

    def testURLs(self):
        config = self.config.copy()
        config['urls.nagios'] ="https://testURLs/zomg/nagios"
        config['urls.graphs'] ="https://testURLs/zomg/graphs"
        for t in ('host', 'service'):
            obj = notify.Notification(t, self.macros[t], config)
            urls = obj.urls()
            self.assert_(urls['nagios'].startswith(config['urls.nagios']))
            self.assert_(urls['graphs'].startswith(config['urls.graphs']))

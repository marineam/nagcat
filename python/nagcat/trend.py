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

"""RRDTool Trending"""

import os
import re

import rrdtool

from nagcat import log, util

_rradir = None

def init(dir):
    global _rradir
    assert dir

    if not os.path.isdir(dir):
        raise util.InitError("%s is not a directory!" % repr(dir))

    if not os.access(dir, os.R_OK | os.W_OK | os.X_OK):
        raise util.InitError("%s is not readable and/or writeable!" % repr(dir))

    _rradir = dir

class Trend(object):

    #: Valid rrdtool data source types
    TYPES = ("GAUGE", "COUNTER", "DERIVE", "ABSOLUTE")

    def __init__(self, host, description, config):
        self.file = self.mkfile(host, description)
        self.conf = config
        self.conf['type'] = self.conf.get('type', "").upper()

        if self.conf['type'] not in self.TYPES:
            raise util.KnownError(
                    "Invalid data source type: %s" % self.conf['type'])

        if os.path.exists(self.file):
            self.validate()
        else:
            self.create()

    @staticmethod
    def mkfile(host, desc):
        host = re.sub("[^a-z0-9_\.]", "", host.lower())
        desc = re.sub("[^a-z0-9_\.]", "", desc.lower())
        file = "%s-%s.rra" % (host, desc)
        return os.path.join(_rradir, file)

    def create(self):
        # For now just create archives identical to how Cacti
        # does since it will be displaying the graphs.
        log.info("Creating RRA: %s" % self.file)
        rrdtool.create(self.file, "--step", "300",
                "DS:default:%s:600:U:U" % self.conf['type'],
                "RRA:AVERAGE:0.5:1:600",
                "RRA:AVERAGE:0.5:6:700",
                "RRA:AVERAGE:0.5:24:755",
                "RRA:AVERAGE:0.5:288:797",
                "RRA:MAX:0.5:1:600",
                "RRA:MAX:0.5:6:700",
                "RRA:MAX:0.5:24:755",
                "RRA:MAX:0.5:288:797")
        self.validate()

    def validate(self):
        info = rrdtool.info(self.file)
        assert info['step'] == 300
        assert info['ds']['default']['type'] == self.conf['type']
        assert info['ds']['default']['minimal_heartbeat'] == 600
        for rra in info['rra']:
            assert rra['cf'] in ('AVERAGE', 'MAX')
            assert rra['xff'] == 0.5
            if rra['pdp_per_row'] == 1:
                assert rra['rows'] == 600
            elif rra['pdp_per_row'] == 6:
                assert rra['rows'] == 700
            elif rra['pdp_per_row'] == 24:
                assert rra['rows'] == 755
            elif rra['pdp_per_row'] == 288:
                assert rra['rows'] == 797
            else:
                assert 0

    def update(self, time, value):
        try:
            float(value)
        except ValueError:
            # Value is not a number so mark it unknown.
            value = "U"
        log.info("Updating %s with %s" % (self.file, value))
        rrdtool.update(self.file, "%s:%s" % (time, value))

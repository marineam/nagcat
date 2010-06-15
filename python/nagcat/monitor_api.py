# Copyright 2009 ITA Software, Inc.
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

import os
import re
import gc
import time
import threading
from resource import getrusage, RUSAGE_SELF

try:
    from lxml import etree
except ImportError:
    etree = None

from twisted.web import resource, server

from nagcat import errors

# Enable/Disable dangerous monitors
# USE ONLY FOR DEBUGGING!
DANGER = False

class XMLPage(resource.Resource, object):
    """Generic XML Page"""

    isLeaf = True

    def xml(self, request):
        """The XML representation of this page.

        Returns an etree.Element object.
        """
        raise Exception("Not Implemented")

    def render_GET(self, request):
        """Transform the xml to text and send it"""
        return etree.tostring(self.xml(request), pretty_print=True)

class Ping(XMLPage):
    """Minimal alive page"""

    def xml(self, request):
        return etree.Element("ok", version="1.0")

def _class_count(objects):
    """List the most common object classes"""

    totals = {}
    for obj in objects:
        try:
            cls = obj.__class__
        except AttributeError:
            cls = type(obj)
        name =  "%s.%s" % (cls.__module__, cls.__name__)
        try:
            totals[name].append(obj)
        except KeyError:
            totals[name] = [obj]

    totals = totals.items()
    totals.sort(lambda a,b: cmp(len(a[1]),len(b[1])))
    totals = totals[-20:] # Is this a reasonable filter?
    return totals

def _class_list(parent, section, objects, refs):
    """Print the most common classes as xml"""

    sec = etree.SubElement(parent, section, count=str(len(objects)))

    for cls, objs in _class_count(objects):
        obj = etree.SubElement(sec, "Object", type=cls, count=str(len(objs)))
        if refs:
            _class_list(obj, "Referrers", gc.get_referrers(*objs), False)

class Objects(XMLPage):
    """Process memory usage"""

    def xml(self, request):
        # include referrers for /stat/memory/referrers
        # this is *REALY* expensive, marked as dangerous
        refs = (DANGER and request.postpath and
                request.postpath[0] == 'referrers')

        mem = etree.Element("Objects", version="1.0")
        _class_list(mem, "Allocated", gc.get_objects(), refs)
        _class_list(mem, "Uncollectable", gc.garbage, refs)
        return mem

class Memory(XMLPage):
    """Process memory usage"""

    vm_regex = re.compile("^(Vm\w+):\s+(\d+)\s+(\w+)$")

    def xml(self, request):
        mem = etree.Element("Memory", version="1.0")
        status = open("/proc/self/status")

        for line in status:
            match = self.vm_regex.match(line)
            if not match:
                continue
            new = etree.SubElement(mem, match.group(1), units=match.group(3))
            new.text = match.group(2)

        status.close()
        return mem

class Time(XMLPage):
    """Process stats"""

    def __init__(self):
        XMLPage.__init__(self)
        self.start_time = self.proc_start()

    @staticmethod
    def proc_start():
        """Find the process start time in seconds since epoch"""

        fd = open("/proc/self/stat")
        start_clk = int(fd.readline().split()[21])
        start_sec = start_clk // os.sysconf("SC_CLK_TCK")
        fd.close()

        fd = open("/proc/stat")
        boot_sec = None
        for line in fd:
            if line.startswith("btime"):
                boot_sec = int(line.split()[1])
        assert boot_sec is not None
        fd.close()

        return boot_sec + start_sec

    def xml(self, request):
        proc = etree.Element("Time", version="1.0")

        status = getrusage(RUSAGE_SELF)
        utime = etree.SubElement(proc, "User", units="seconds")
        utime.text = str(status.ru_utime)
        stime = etree.SubElement(proc, "System", units="seconds")
        stime.text = str(status.ru_stime)
        start = etree.SubElement(proc, "Uptime", units="seconds")
        start.text = str(int(time.time()) - self.start_time)

        return proc

class Threads(XMLPage):
    """Process threads"""

    def xml(self, request):
        threads = threading.enumerate()
        all = etree.Element("Threads", count=str(len(threads)), version="1.0")

        for thread in threads:
            this = etree.SubElement(all, "Thread")
            name = etree.SubElement(this, "Name")
            name.text = str(thread.name)
            if hasattr(thread, 'ident'):
                id = etree.SubElement(this, "Id")
                id.text = str(thread.ident)

        return all

class Stat(XMLPage):
    """The main /stat page"""

    isLeaf = False

    def __init__(self):
        XMLPage.__init__(self)

        # self.children is a dict but we want the order to be
        # predictable to avoid surprising people using this page.
        self.order = []

        self.putChild("", self)

        # Pages to include in the complete XML page
        self.includeChild("ping", Ping())
        self.includeChild("memory", Memory())
        self.includeChild("time", Time())
        self.includeChild("threads", Threads())

        # Pages to exclude from the complete page
        self.putChild("objects", Objects())

    def includeChild(self, path, child):
        XMLPage.putChild(self, path, child)
        if path not in self.order:
            self.order.append(path)

    def xml(self, request):
        stat = etree.Element("Stat")

        for path in self.order:
            child = self.children[path]
            stat.append(child.xml(request))

        return stat

class MonitorSite(server.Site):
    """The whole monitoring api wrapped up in dark chocolate"""

    noisy = False

    def __init__(self):
        if etree is None:
            raise errors.InitError("lxml is required for the monitoring api")

        self.stat = Stat()
        self.root = resource.Resource()
        self.root.putChild("stat", self.stat)
        server.Site.__init__(self, self.root)

    def includeChild(self, path, child):
        self.stat.includeChild(path, child)

    def putChild(self, path, child):
        self.stat.putChild(path, child)

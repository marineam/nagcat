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

from railroad.pathsettings import data_path

import rrdtool, os, coil, sys, time
from django.http import HttpResponse
from django.template import Context, loader
from railroad.parserrd.views import graphable


sys.path.append('/ita/installs/nagcat/python')

from nagcat import nagios_objects

stat_file = data_path + 'status.dat'
obj_file = data_path + 'objects.cache'

def hostlist():
    host_list = nagios_objects.ObjectParser(stat_file, ('host',))['host']
    return host_list

def hostdetail(host):
    host_detail = nagios_objects.ObjectParser(obj_file, \
                    ('host',), {'host_name': host})
    return host_detail

def grouplist():
    group_list = nagios_objects.ObjectParser(obj_file,  \
                    ('hostgroup',))['hostgroup']
    return group_list

def servicelist(host):
    objects = nagios_objects.ObjectParser(obj_file,     \
                    ('host',), {'host_name': host})
    status = nagios_objects.ObjectParser(stat_file,     \
                    ('host','service'), {'host_name': host})
    host_conf = objects['host'][0]

    services = ""
    service_list = status['service']
    service_list = zip(service_list, graphable(host, service_list))
    return service_list

def servicedetail(host, service):
    status = nagios_objects.ObjectParser(stat_file, ('service'),    \
                {'host_name': host, 'service_description': service})
    service_dict = status['service'][0]

    str = service_dict.get('plugin_output','')
    if str:
        str += '\n'
        str += service_dict.get('long_plugin_output','')
    
    return str

def get_time_intervals():
    intervals = [86400,604800,2592000,31104000]
    times = ['Day','Week','Month','Year']
    ending = int(time.time())
    return zip(times, [[ending-interval, ending] for interval in intervals])

# TODO: This should probably just be a class that wraps Context, as we
# will have to include this on each and every page
def add_hostlist(c):
    groups = grouplist()
    hosts = hostlist()
    for host in hosts:
        host['group'] = '(no group)'
        for group in groups:
            if host['host_name'] in group['members'].split(','):
                host['group'] = group['alias']
    c['groups'] = groups
    c['hosts'] =  hosts
    return c

def index(request):
    t = loader.get_template('index.html')
    context_data = {}
    context_data = add_hostlist(context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def host(request, host):
    t = loader.get_template('host.html')
    services = servicelist(host)
    host_detail = hostdetail(host)
    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'host_name': host,
        'host': host_detail,
        'services': services,
        'time_interval': [starting,ending]
    }
    
    context_data = add_hostlist(context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def service(request, host, service):
    t = loader.get_template('service.html')
    service_detail = servicedetail(host, service)
    time_intervals = get_time_intervals()
    context_data = {
        'host_name': host,
        'service_name': service,
        'service': service_detail,
        'time_intervals': time_intervals
    }

    context_data = add_hostlist(context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

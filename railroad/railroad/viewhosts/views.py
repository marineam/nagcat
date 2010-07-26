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


import rrdtool, os, coil, sys, time
from django.conf import settings
from django.http import HttpResponse
from django.template import Context, loader
from railroad.parserrd.views import graphable, is_graphable
from nagcat import nagios_objects
from railroad.errors import RailroadError

data_path = settings.DATA_PATH
stat_file = data_path + 'status.dat'
obj_file = data_path + 'objects.cache'

def hostlist():
    host_list = nagios_objects.ObjectParser(stat_file, ('host',))['host']
    return host_list

def hostlist_by_group(group):
    group_list = nagios_objects.ObjectParser(obj_file, ('hostgroup'), {'alias': group})['hostgroup']
    try:
        group_dict = group_list[0]
        return group_dict['members'].split(',')
    except IndexError as e:
        raise RailroadError(group + ' not found in objects.cache')

def hostdetail(host):
    try:
        host_detail = nagios_objects.ObjectParser(stat_file, \
                        ('host',), {'host_name': host})['host']
        return host_detail[0]
    except IndexError as e:
        raise RailroadError(group + ' not found in objects.cache')

def grouplist():
    group_list = nagios_objects.ObjectParser(obj_file,  \
                    ('hostgroup',))['hostgroup']
    return group_list

def servicelist(host):
    status = nagios_objects.ObjectParser(stat_file,     \
                    ('service'), {'host_name': host})
    services = ""
    service_list = status['service']
    service_list = zip(service_list, graphable(host, service_list))
    return service_list

def servicedetail(host, service):
    service_list = nagios_objects.ObjectParser(stat_file, ('service'),  \
                {'host_name': host, 'service_description': service})
    try:
        return service_list['service'][0]
    except KeyError as e:
        return None
    except IndexError as e:
        return None


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

    str = service_detail.get('plugin_output','')
    if str:
        str += '\n'
        str += service_detail.get('long_plugin_output','')
    
    time_intervals = get_time_intervals()
    context_data = {
        'host_name': host,
        'service_name': service,
        'service_output': str,
        'graphable': is_graphable(host, service),
        'true': True,
        'time_intervals': time_intervals
    }

    context_data = add_hostlist(context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def group(request, group):
    t = loader.get_template('group.html')
    host_names = hostlist_by_group(group)
    service_set = set([])

    host_list = map(hostdetail, host_names)

    for host in host_names:
        service_list = servicelist(host)
        mapped = map(lambda x: x[0]['service_description'], service_list)
        new_set = set(mapped)
        service_set = service_set.union(new_set)

    services = list(service_set)

    hostlen = len(host_list)
    servicelen = len(services)
    
    if (servicelen > hostlen):
        host_list.extend([None] * (servicelen-hostlen))
    else:
        services.extend([None] * (hostlen-servicelen))

    members = zip(host_list,services)

    
    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'group_name': group,
        'members': members,
        'time_interval': [starting,ending]
    }
    
    context_data = add_hostlist(context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def groupservice(request, group, service):
    t = loader.get_template('groupservice.html')
    host_names = hostlist_by_group(group)
    host_list = map(hostdetail, host_names)

    def checkgraphable (host):
        serv = servicedetail(host, service)
        if serv:
            serv['graphable'] = is_graphable(host, service)
        return serv
        
    services = [checkgraphable(host) for host in host_names]

    members = zip(host_list, services)

    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'group_name': group,
        'service_name': service,
        'members': members,
        'time_interval': [starting,ending],
        'true': True
    }
    
    context_data = add_hostlist(context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

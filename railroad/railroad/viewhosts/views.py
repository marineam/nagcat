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
    try:
        return nagios_objects.ObjectParser(stat_file, ('host',))['host']
    except IndexError as e:
        raise RailroadError('Unexpected ObjectParser failure')


def hostlist_by_group(group):
    group_list = nagios_objects.ObjectParser(obj_file, ('hostgroup'), {'alias': group})['hostgroup']
    all_hosts = hostlist()
    host_list = []
    try:
        group_dict = group_list[0]
        target = group_dict['members'].split(',')
        for host in all_hosts:
            if host['host_name'] in target:
                host_list.append(host)
        return host_list
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
    sidebar = []

    for group in groups:
        group_name = group['alias']
        addinghosts = group['members'].split(',')
        hosts_of_group = []
        for added in addinghosts:
            for host in hosts:
                if host['host_name'] == added:
                    hosts_of_group.append(host) 
                    host['has_group'] = True
                    break
        sidebar.append((group_name, hosts_of_group))

    no_group = filter(lambda x: not(x.has_key('has_group')), hosts)
    if len(no_group):
        sidebar.append(('(no group)', no_group))
    c['sidebar'] = sidebar
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
    service_dict = {}
        
    host_list = hostlist_by_group(group)
    host_names = map(lambda x: x['host_name'], host_list)

    def test():
        test1 = nagios_objects.ObjectParser(stat_file, ('service','host'), )
        test2 = nagios_objects.ObjectParser(obj_file, ('host_group'), )

    test()

    service_list = nagios_objects.ObjectParser(stat_file, ('service'), {'host_name': host_names})['service']

    for service in service_list:
        service_name = service['service_description']
        if service_name in service_dict:
            continue

        service_dict[service_name] = service['host_name'] in host_names

    services = filter(lambda x: service_dict[x], service_dict.keys())
    host_list.sort(lambda x,y: cmp(x['host_name'],y['host_name']))
    services.sort()

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
    host_list = hostlist_by_group(group)
    service_list = nagios_objects.ObjectParser(stat_file, ('service'),  \
                        {'service_description': service})['service']

    def has_service(host):
        for service in service_list:
           if service['host_name'] == host:
               return True

        return False
        
    host_list = filter(lambda x: has_service(x['host_name']), host_list)
    target = map(lambda x: x['host_name'], host_list)
    service_list = filter(lambda x: x['host_name'] in target, service_list)
    host_list.sort(lambda x,y: cmp(x['host_name'],y['host_name']))
    service_list.sort(lambda x,y: cmp(x['host_name'],y['host_name']))

    for s in service_list:
        s['is_graphable'] = is_graphable(s['host_name'], s['service_description'])

    members = zip(host_list, service_list)

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

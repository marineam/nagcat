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


import rrdtool, os, coil, sys, time, re
from django.conf import settings
from django.http import HttpResponse
from django.template import Context, loader
from nagcat import nagios_objects
from railroad.errors import RailroadError

def is_graphable(host, service):
    rra_path = settings.RRA_PATH
    coilfile = rra_path + host + '/' + service + '.coil'
    rrd = rra_path + host + '/' + service + '.rrd'
    if(os.path.exists(coilfile) and os.path.exists(rrd)):
        coilstring = open(coilfile).read()
        coilstruct = coil.parse(coilstring)
        query = coilstruct.get('query')

        # rrdtool hates unicode strings, and Django gives us one, 
        # so convert to ascii
        rrdslice = rrdtool.fetch(str(rrd),
                    '--start', '0',
                    '--end', '10',
                    '--resolution', '1',
                    'AVERAGE')

        try:
            rrdslice[1].index('_state')
            return True
        except ValueError:
            for key in query.keys():
                val = query.get(key)
                if type() == type(query) and val.has_key('trend'):
                    return True
            return False
    return False


def are_graphable(host, service_list):
    rra_path = settings.RRA_PATH
    for service in service_list:
        coilfile = rra_path + host + '/'    \
            + service['service_description'] + '.coil'
        rrd = rra_path + host + '/'         \
            + service['service_description'] + '.rrd'
        if(os.path.exists(coilfile) and os.path.exists(rrd)):
            coilstring = open(coilfile).read()
            coilstruct = coil.parse(coilstring)
            query = coilstruct.get('query')

            # rrdtool hates unicode strings, and Django gives us one, 
            # so convert to ascii
            rrdslice = rrdtool.fetch(str(rrd),
                        '--start', '0',
                        '--end', '10',
                        '--resolution', '1',
                        'AVERAGE')

            try:
                rrdslice[1].index('_state')
                service['is_graphable'] = True
            except ValueError:
                for key in query.keys():
                    val = query.get(key)
                    if type() == type(query) and val.has_key('trend'):
                        service['is_graphable'] = True
                        break
                service['is_graphable'] = False

        else:
            service['is_graphable'] = False

def parse():
    data_path = settings.DATA_PATH
    stat_path = data_path + 'status.dat'
    obj_path = data_path + 'objects.cache'
    stat = nagios_objects.ObjectParser(stat_path, ('service','host'),)
    obj = nagios_objects.ObjectParser(obj_path, ('hostgroup'), )
    return stat,obj

def grouplist(obj):
    return obj['hostgroup']

def hostlist(stat):
    return stat['host']

def servicelist(stat):
    return stat['service']

def groupdetail(obj, group_name):
    group_list = grouplist(obj)
    for group in group_list:
        if group['alias'] == group_name:
            return group

def hostdetail(stat, host_name):
    host_list = hostlist(stat)
    for host in host_list:
        if host['host_name'] == host_name:
            return host

def servicelist_by_description(stat, service_description):
    all_services = servicelist(stat)
    return [service for service in all_services if service['service_description'] == service_description]

def servicedetail(stat, host, service_name):
    all_services = servicelist(stat)
    for service in all_services:
        if service['host_name'] == host and service['service_description'] == service_name:
            return service

def hostlist_by_group(stat, obj, group_name):
    group = groupdetail(obj, group_name)
    all_hosts = hostlist(stat)
    target = group['members'].split(',')
    return [host for host in all_hosts if host['host_name'] in target]

def servicelist_by_host(stat, host):
    all_services = servicelist(stat)
    return [service for service in all_services if service['host_name'] == host]


def get_time_intervals():
    intervals = [86400,604800,2592000,31104000]
    times = ['day','week','month','year']
    ending = int(time.time())
    return zip(times, [[ending-interval, ending] for interval in intervals])

# TODO: This should probably just be a class that wraps Context, as we
# will have to include this on each and every page
def add_hostlist(stat, obj, c):
    groups = grouplist(obj)
    groups.sort(lambda x,y: cmp(x['alias'],y['alias']))
    hosts = hostlist(stat)
    sidebar = []
    for group in groups:
        group_name = group['alias']
        addinghosts = group['members'].split(',')
        hosts_of_group = []
        for host in hosts:
            if host['host_name'] in addinghosts:
                hosts_of_group.append(host) 
                host['has_group'] = True
        hosts_of_group.sort(lambda x,y: cmp(x['host_name'],y['host_name']))
        sidebar.append((group_name, hosts_of_group))
    no_group = filter(lambda x: not(x.has_key('has_group')), hosts)
    if len(no_group):
        sidebar.append(('(no group)', no_group))
    c['sidebar'] = sidebar
    return c

def index(request):
    t = loader.get_template('index.html')
    stat,obj = parse()
    context_data = {}
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def host(request, host):
    t = loader.get_template('host.html')
    stat,obj = parse()
    services = servicelist_by_host(stat, host)
    services.sort(lambda x,y: cmp(x['service_description'],y['service_description']))
    are_graphable(host, services)
    host_detail = hostdetail(stat, host)
    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'host_name': host,
        'host': host_detail,
        'services': services,
        'true' : True,
        'time_interval': [starting,ending]
    }
    
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def service(request, host, service):
    t = loader.get_template('service.html')
    stat,obj = parse()
    service_detail = servicedetail(stat, host, service)

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

    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def group(request, group):
    t = loader.get_template('group.html')
    stat,obj = parse()
    service_dict = {}
        
    host_list = hostlist_by_group(stat, obj, group)
    host_names = map(lambda x: x['host_name'], host_list)

    service_list = servicelist(stat)

    for service in service_list:
        service_name = service['service_description']
        if service['host_name'] in host_names:
            service_dict[service_name] = True

    services = service_dict.keys()
    host_list.sort(lambda x,y: cmp(x['host_name'],y['host_name']))
    services.sort()

    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'group_name': group,
        'hosts': host_list,
        'services': services,
        'time_interval': [starting,ending]
    }
    
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def groupservice(request, group, service):
    t = loader.get_template('groupservice.html')
    stat,obj = parse()
    host_list = hostlist_by_group(stat, obj, group)
    service_list = servicelist_by_description(stat, service)

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
    
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

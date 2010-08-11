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

import json
import os
import sys
import re
import time
import pickle

import coil
import rrdtool
from django.conf import settings
from django.http import HttpResponse
from django.template import Context, loader
from nagcat import nagios_objects

from railroad.errors import RailroadError
from railroad.viewhosts.models import URL

def is_graphable(host, service):
    rra_path = settings.RRA_PATH
    coilfile = rra_path + host + '/' + service + '.coil'
    rrd = rra_path + host + '/' + service + '.rrd'
    if os.path.exists(coilfile) and os.path.exists(rrd):
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
        if os.path.exists(coilfile) and os.path.exists(rrd):
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
    stat = nagios_objects.ObjectParser(stat_path, ('service', 'host'))
    obj = nagios_objects.ObjectParser(obj_path, ('hostgroup'))
    return stat, obj

def grouplist(obj):
    return obj['hostgroup']

def hostlist(stat):
    return stat['host']

def servicelist(stat):
    return stat['service']

def groupnames(obj):
    return map(lambda x: x['alias'], obj['hostgroup'])

def hostnames(stat):
    return map(lambda x: x['host_name'], stat['host'])

def servicenames(stat):
    return map(lambda x: x['service_description'], stat['service'])

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
    return [service for service in all_services \
                if service['service_description'] == service_description]

def servicedetail(stat, host, service_alias):
    all_services = servicelist(stat)
    for service in all_services:
        if service['host_name'] == host and \
                service['service_description'] == service_alias:
            return service

def hostlist_by_group(stat, obj, group_name):
    group = groupdetail(obj, group_name)
    all_hosts = hostlist(stat)
    target = group['members'].split(',')
    return [host for host in all_hosts if host['host_name'] in target]

def hostnames_by_group(stat, obj, group_name):
    group = groupdetail(obj, group_name)
    return group['members'].split(',')

def hostlist_by_service(stat, service):
    all_services = servicelist(stat)
    return [hostdetail(stat, s['host_name']) for s in all_services  \
                                if s['service_description'] == service]

def hostnames_by_service(stat, service):
    all_services = servicelist(stat)
    return [s['host_name'] for s in all_services    \
                                if s['service_description'] == service]

def servicelist_by_host(stat, host):
    all_services = servicelist(stat)
    return [service for service in all_services \
                                if service['host_name'] == host]

def servicenames_by_host(stat, host):
    all_services = servicelist(stat)
    return [service['service_description'] for service in all_services  \
                                if service['host_name'] == host]

def get_time_intervals():
    #            day  , week  , month  , year
    intervals = [86400, 604800, 2592000, 31104000]
    times = ['day', 'week', 'month', 'year']
    ending = int(time.time())
    return zip(times, [[ending-interval, ending] for interval in intervals])

# TODO: This should probably just be a class that wraps Context, as we
# will have to include this on each and every page
def add_hostlist(stat, obj, c):
    groups = grouplist(obj)
    groups.sort(lambda x, y: cmp(x['alias'], y['alias']))
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
        hosts_of_group.sort(lambda x, y: cmp(x['host_name'], y['host_name']))
        sidebar.append((group_name, hosts_of_group))
    no_group = filter(lambda x: not(x.has_key('has_group')), hosts)
    if len(no_group):
        sidebar.append(('(no group)', no_group))
    c['sidebar'] = sidebar
    return c

def index(request):
    t = loader.get_template('index.html')
    stat, obj = parse()
    context_data = {}
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def host(request, host):
    t = loader.get_template('host.html')
    stat, obj = parse()
    services = servicelist_by_host(stat, host)
    services.sort(lambda x, y:  \
                     cmp(x['service_description'], y['service_description']))
    are_graphable(host, services)
    host_detail = hostdetail(stat, host)
    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'host_name': host,
        'host': host_detail,
        'services': services,
        'true' : True,
        'time_interval': [starting, ending],
        'graphs': True,
    }
    
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def service(request, host, service):
    t = loader.get_template('service.html')
    stat, obj = parse()
    service_detail = servicedetail(stat, host, service)

    str = service_detail.get('plugin_output', '')
    if str:
        str += '\n'
        str += service_detail.get('long_plugin_output', '')
    
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
    stat, obj = parse()
    service_dict = {}
        
    host_list = hostlist_by_group(stat, obj, group)
    host_names = map(lambda x: x['host_name'], host_list)
    service_list = servicelist(stat)

    # Handles removing unique digits, dashes, commas, and version numbers
    # Duplicated in groupservice
    janitor = re.compile("[-,]?\d+\.?\d*[-,]?")

    for service in service_list:
        service_alias = janitor.sub("", service['service_description'])
        service_test = service.get('_TEST', None)
        service_test = service_test if service_test \
                                    else service['check_command']
        if service['host_name'] in host_names:
            if not(service_dict.get(service_test, None)):
                service_dict[service_test] = []
            if not (service_alias in service_dict[service_test]):
                service_dict[service_test].append(service_alias)

    services = []
    service_tests = service_dict.keys()
    for service_test in service_tests:
        #prefix = os.path.commonprefix(service_dict[service_test])
        #suffix = os.path.commonprefix(map(lambda x: x[:len(prefix):-1],    \
                                            #service_dict[service_test]))[::-1]
        #d = locals()
        #service = ('%(prefix)s' % d) + ('%(suffix)s' % d)
        for service_alias in service_dict[service_test]:
            services.append({'service_test': service_test,  \
                                'service_alias' : service_alias})

    services.sort(lambda x, y: cmp(x['service_alias'], y['service_alias']))
    host_list.sort(lambda x, y: cmp(x['host_name'], y['host_name']))

    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'group_name': group,
        'hosts': host_list,
        'services': services,
        'time_interval': [starting, ending]
    }
    
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def groupservice(request, group, test, alias):
    t = loader.get_template('groupservice.html')
    stat, obj = parse()
    host_list = hostlist_by_group(stat, obj, group)
    target = map(lambda x: x['host_name'], host_list)
    all_services = servicelist(stat)

    janitor = re.compile("[-,]?\d+\.?\d*[-,]?")
    for service in all_services:
        service_test = service.get('_TEST', None) if        \
                       service.get('_TEST', None) else      \
                       service.get('check_command', None)
        service_alias = janitor.sub("", service['service_description'])

        if service_test == test and service_alias == alias:
            host_name = service['host_name']
            try: 
                host = host_list[target.index(host_name)]
                if not(host.has_key('services')): host['services'] = []
                service['is_graphable'] =   \
                    is_graphable(host_name, service['service_description'])
                host['services'].append(service)
            except ValueError:
                continue
                
    host_list = filter(lambda x: x.has_key('services'), host_list)
    host_list.sort(lambda x, y: cmp(x['host_name'], y['host_name']))
    map(lambda z: z['services'].sort(lambda x, y:   \
        cmp(x['service_description'], y['service_description'])), host_list)

    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'group_name': group,
        'service_alias': alias,
        'host_list': host_list,
        'time_interval': [starting, ending],
        'true': True,
        'graphs': True,
    }
    
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def form(request):
    t = loader.get_template('form.html')
    stat, obj = parse()
    group_list = grouplist(obj)
    group_list.sort(lambda x,y: cmp(x['alias'], y['alias']))
    host_list = hostlist(stat)
    host_list.sort(lambda x,y: cmp(x['host_name'], y['host_name']))
    service_list = list(set(map(lambda x: x['service_description'], \
                                            servicelist(stat))))
    service_list.sort()

    ending = int(time.time())
    starting = ending - 86400
    context_data = {
        'group_list': group_list,
        'host_list': host_list,
        'service_list': service_list,
        'time_interval': [starting, ending]
    }
    c = Context(context_data)
    return HttpResponse(t.render(c))

def customgraph(request):
    querydict = request.GET

    stat,obj = parse()

    t = loader.get_template('graph.html')

    format = [('type0','value0'), ('type1','value1'), ('type2','value2')]
    typeDict = {'group': [], 'host': [], 'service': [], }

    for match in format:
        type = querydict.get(match[0], '').lower()
        val = querydict.get(match[1], '')
        if type and val:
            typeDict[type] = val

    group = typeDict['group']
    host = typeDict['host']
    service = typeDict['service']

    service_list = []

    if not(service):
        if host:
            service_list = servicelist_by_host(stat, host)
            service_list.sort(lambda x, y:  \
                cmp(x['service_description'], y['service_description']))
            are_graphable(host, service_list)
        else:
            return HttpResponse('')
    else:
        if host:
            service_detail = servicedetail(stat, host, service)
            service_detail['is_graphable'] = is_graphable(host, service)
            service_list = [service_detail]
        elif group:
            target = hostnames_by_group(stat, obj, group)
            all_services = servicelist(stat)

            service_list = [s for s in all_services \
                if s['service_description'] == service  \
                and s['host_name'] in target]
            for x in service_list: 
                x['is_graphable'] = \
                    is_graphable(x['host_name'], x['service_description'])

            #host_list = filter(lambda x: x.has_key('services'), host_list)
            #host_list.sort(lambda x, y: cmp(x['host_name'], y['host_name']))
            #map(lambda z: z['services'].sort(lambda x, y:  \
            #cmp(x['service_description'], y['service_description'])),  \
            #host_list)

        
    ending = int(time.time())
    starting = ending - 86400

    context_data = {
        'host_name': host,
        'service_list': service_list,
        'time_interval': [starting, ending], 
        'true': True,
    }
    c = Context(context_data)
    return HttpResponse(t.render(c))

def configurator(request, id=None):
    t = loader.get_template('configurator.html')
    stat, obj = parse()
    group_list = grouplist(obj)
    group_list.sort(lambda x,y: cmp(x['alias'], y['alias']))
    host_list = hostlist(stat)
    host_list.sort(lambda x,y: cmp(x['host_name'], y['host_name']))
    service_list = list(set(    \
        map(lambda x: x['service_description'], servicelist(stat))))
    service_list.sort()

    loaded_graphs = []
    if id != None:
        content = pickle.loads(str(URL.objects.get(id=id)))
        loaded_graphs = map(lambda (host,service,start,end):  \
            [hostdetail(stat, host), servicedetail(stat, host, service),    \
                start, end], content)

    context_data = {
        'loaded_graphs': loaded_graphs,
        'group_list': group_list,
        'host_list': host_list,
        'service_list': service_list,
        'graphs': True,
    }
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def generatelink(request):
    querydict = request.POST 
    if not(querydict):
        querydict = request.GET

    raw = querydict.get('services', '')
    #return HttpResponse(raw)
    list = json.loads(querydict.get('services', ''))
    #return HttpResponse(str(list))
    typez = type(list)
    import types
    content = pickle.dumps(list)
    link = URL(content=content)
    link.save()
    return HttpResponse(json.dumps(link.id))

def stripstate(state):
    state['group'] = map(lambda x: x['alias'], state['group'])
    state['host'] = map(lambda x: x['host_name'], state['host'])
    state['service'] = list(    \
        set(map(lambda x: x['service_description'], state['service'])))
    state['service'].sort()
    return state

def selectgroup(state, group_name):
    service_list = []

    group_list = state['group']
    for group in group_list:
        if group['alias'] == group_name:
            break

    target = group['members'].split(',')
    host_list = [host for host in state['host'] if host['host_name'] in target]
    all_services = state['service']

    service_list.extend([service for service in all_services    \
        if service['host_name'] in map(lambda x: x['host_name'], host_list)])
    state['group'] = []
    state['host'] = host_list
    state['service'] = service_list

def selecthost(state, host):
    all_services = state['service']
    state['group'] = []
    state['host'] = []
    state['service'] = [service for service in all_services \
        if service['host_name'] == host]

def selectservice(state, service):
    all_services = state['service']
    host_names = [s['host_name'] for s in all_services  \
        if s['service_description'] == service]
    host_list = [host for host in state['host'] if  \
        host['host_name'] in host_names]
    group_list = [group for group in state['group'] if  \
        not(all(map(lambda x: not(x in host_names), \
            group['members'].split(','))))]
    state['group'] = group_list
    state['host'] = host_list
    state['service'] = []

def formstate(request):
    querydict = request.GET
    stat,obj = parse()
    state =                                         \
        {                                           \
         'options': ['group', 'host', 'service'],   \
         'group': grouplist(obj),                   \
         'host': hostlist(stat),                    \
         'service': servicelist(stat),              \
         }
    if (not(querydict)):
        state['options'] =  \
            map(lambda x: x[0].upper() + x[1:], state['options'])
        return HttpResponse(json.dumps(stripstate(state)))

    format = [('type0','value0'), ('type1','value1'), ('type2','value2')]
    typeDict = {'group': [], 'host': [], 'service': [], }

    for match in format:
        type = querydict.get(match[0], '').lower()
        val = querydict.get(match[1], '')
        if type and val and type in typeDict:
            typeDict[type] = val

    group = typeDict['group']
    host = typeDict['host']
    service = typeDict['service']

    if group:
        selectgroup(state, group)
    if host:
        selecthost(state, host)
    if service:
        selectservice(state, service)


    state['options'] = [option for option in typeDict.keys()    \
                                 if not(typeDict[option])]
    if host and 'group' in state['options']:
        state['options'].remove('group')

    state['options'] = map(lambda x: x[0].upper() + x[1:], state['options'])
    
    state['ready'] = False
    if host:
        state['ready'] = True
    elif service and group:
        state['ready'] = True

    return HttpResponse(json.dumps(stripstate(state)))

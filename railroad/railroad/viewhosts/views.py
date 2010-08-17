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
from django.http import HttpResponse, HttpRequest
from django.template import Context, loader
from nagcat import nagios_objects

from railroad.errors import RailroadError
from railroad.viewhosts.models import URL

DAY = 86400

def is_graphable(host, service):
    """Checks if service of host is graphable (has state or trend)"""
    rra_path = settings.RRA_PATH
    coilfile = '%s%s/%s.coil' % (rra_path, host, service)
    rrd = '%s%s/%s.rrd' % (rra_path, host, service)

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
    """Flags services of host that are graphable (has state or trend)"""
    rra_path = settings.RRA_PATH
    for service in service_list:
        coilfile = '%s%s/%s.coil' % \
            (rra_path, host, service['service_description'])
        rrd = '%s%s/%s.rrd' % (rra_path, host, service['service_description'])
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
    """Uses nagcat's nagios object parser to get host,service,group details"""
    data_path = settings.DATA_PATH
    stat_path = '%sstatus.dat' % data_path
    obj_path = '%sobjects.cache' % data_path 
    stat = nagios_objects.ObjectParser(stat_path, ('service', 'host'))
    obj = nagios_objects.ObjectParser(obj_path, ('hostgroup'))
    return stat, obj

def grouplist(obj):
    """Returns a list of groups"""
    return obj['hostgroup']

def hostlist(stat):
    """Returns a list of hosts"""
    return stat['host']

def servicelist(stat):
    """Returns a list of services"""
    return stat['service']

def groupnames(obj):
    """Returns a list of groups names"""
    return map(lambda x: x['alias'], obj['hostgroup'])

def hostnames(stat):
    """Returns a list of host names"""
    return map(lambda x: x['host_name'], stat['host'])

def servicenames(stat):
    """Returns a list of service names"""
    return map(lambda x: x['service_description'], stat['service'])

def groupdetail(obj, group_name):
    """Returns the group object with the specified name"""
    group_list = grouplist(obj)
    for group in group_list:
        if group['alias'] == group_name:
            return group

def hostdetail(stat, host_name):
    """Returns the host object with the specified name"""
    host_list = hostlist(stat)
    for host in host_list:
        if host['host_name'] == host_name:
            return host

def servicelist_by_description(stat, service_description):
    """Returns a list of service objects with the specified name"""
    all_services = servicelist(stat)
    return [service for service in all_services \
                if service['service_description'] == service_description]

def servicedetail(stat, host, service_alias):
    """Returns the service object with the specified name and host"""
    all_services = servicelist(stat)
    for service in all_services:
        if service['host_name'] == host and \
                service['service_description'] == service_alias:
            return service

def hostlist_by_group(stat, obj, group_name):
    """Returns a list of hosts with the specified group"""
    group = groupdetail(obj, group_name)
    all_hosts = hostlist(stat)
    target = group['members'].split(',')
    return [host for host in all_hosts if host['host_name'] in target]

def hostnames_by_group(stat, obj, group_name):
    """Returns a list of host names with the specified group"""
    group = groupdetail(obj, group_name)
    return group['members'].split(',')

def hostlist_by_service(stat, service):
    """Returns a list of hosts possessing the specified service"""
    all_services = servicelist(stat)
    return [hostdetail(stat, s['host_name']) for s in all_services  \
                                if s['service_description'] == service]

def hostnames_by_service(stat, service):
    """Returns a list of hosts (names) possessing the specified service"""
    all_services = servicelist(stat)
    return [s['host_name'] for s in all_services    \
                                if s['service_description'] == service]

def servicelist_by_host(stat, host):
    """Returns a list of services possessed by the specified host"""
    all_services = servicelist(stat)
    return [service for service in all_services \
                                if service['host_name'] == host]

def servicenames_by_host(stat, host):
    """Returns a list of services (names) possessed by the specified host"""
    all_services = servicelist(stat)
    return [service['service_description'] for service in all_services  \
                                if service['host_name'] == host]

def get_time_intervals():
    """Returns a list of (start,end) intervals for day, week, month, year"""
    #            day  , week  , month  , year
    intervals = [86400, 604800, 2592000, 31104000]
    times = ['day', 'week', 'month', 'year']
    end = int(time.time())
    return zip(times, [[end-interval, end] for interval in intervals])

# TODO: This should probably just be a class that wraps Context, as we
# will have to include this on each and every page
def add_hostlist(stat, obj, c):
    """Returns the given context with the sidebar filled in"""
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
    """Returns the index page"""
    t = loader.get_template('index.html')
    stat, obj = parse()
    context_data = {}
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def host(request, host):
    """Returns a page showing all services of the specified host"""
    loaded_graphs = []
    stat, obj = parse()
    if host != None:
        end = int(time.time())
        start = end - DAY
        loaded_graphs = servicelist_by_host(stat, host)
        loaded_graphs.sort(lambda x,y: cmp(x['service_description'],    \
                                         y['service_description']))
        for graph in loaded_graphs:
            graph['is_graphable'] = \
                is_graphable(host, graph['service_description'])
            graph['start'] = start
            graph['end'] = end
            graph['period'] = 'ajax'
         
    return configurator(stat, obj,  \
        'Host Detail: %s' % host, host, loaded_graphs)

def service(request, host, service):
    """Returns a page showing service details of specified service of host"""
    t = loader.get_template('service.html')
    stat, obj = parse()
    service_detail = servicedetail(stat, host, service)

    str = service_detail.get('plugin_output', '')
    if str:
        str = '%s\n%s' % (str, service_detail.get('long_plugin_output', ''))
    
    time_intervals = get_time_intervals()
    context_data = {
        'host_name': host,
        'service_name': service,
        'service_output': str,
        'graphable': is_graphable(host, service),
        'time_intervals': time_intervals
    }

    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def group(request, group):
    """Returns a page showing all hosts/services of the specified group"""
    t = loader.get_template('group.html')
    stat, obj = parse()
    service_dict = {}
        
    host_list = hostlist_by_group(stat, obj, group)
    host_names = map(lambda x: x['host_name'], host_list)
    service_list = servicelist(stat)

    # Remove unique digits, dashes, commas, and version numbers to consolidate
    # service descriptions.  Duplicated in groupservice function
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
        for service_alias in service_dict[service_test]:
            services.append({'service_test': service_test,  \
                                'service_alias' : service_alias})

    services.sort(lambda x, y: cmp(x['service_alias'], y['service_alias']))
    host_list.sort(lambda x, y: cmp(x['host_name'], y['host_name']))

    end = int(time.time())
    start = end - DAY 
    context_data = {
        'group_name': group,
        'hosts': host_list,
        'services': services,
        'time_interval': [start, end]
    }
    
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def groupservice(request, group, test, alias):
    """Returns a page showing all instances of specified service of group"""
    loaded_graphs = []
    stat, obj = parse()
    if group != None and test != None and alias != None:
        end = int(time.time())
        start = end - DAY 
        host_list = hostlist_by_group(stat, obj, group)
        target = map(lambda x: x['host_name'], host_list)

        service_list = servicelist(stat)

        # Filter service_list by test and alias (strip numbers/hyphens)
        janitor = re.compile("[-,]?\d+\.?\d*[-,]?")
        for service in service_list:
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
                    if (service['is_graphable']):
                        service['start'] = start
                        service['end'] = end
                        service['period'] = 'ajax'
                    host['services'].append(service)
                except ValueError:
                    continue
                    
        host_list = filter(lambda x: x.has_key('services'), host_list)
        host_list.sort(lambda x, y: cmp(x['host_name'], y['host_name']))
        map(lambda z: z['services'].sort(lambda x, y:   \
            cmp(x['service_description'], y['service_description'])),   \
                host_list)

        for host in host_list:
            loaded_graphs.extend(host['services'])
    return configurator(stat, obj, 'Group-Service Detail: %s > %s' %    \
            (group, alias), '%s > %s' % (group, alias), loaded_graphs)

def form(request):
    """Returns a form for choosing group/host/service"""
    t = loader.get_template('form.html')
    stat, obj = parse()
    group_list = grouplist(obj)
    group_list.sort(lambda x,y: cmp(x['alias'], y['alias']))
    host_list = hostlist(stat)
    host_list.sort(lambda x,y: cmp(x['host_name'], y['host_name']))
    service_list = list(set(map(lambda x: x['service_description'], \
                                            servicelist(stat))))
    service_list.sort()

    end = int(time.time())
    start = end - DAY
    context_data = {
        'group_list': group_list,
        'host_list': host_list,
        'service_list': service_list,
        'time_interval': [start, end]
    }
    c = Context(context_data)
    return HttpResponse(t.render(c))

def customgraph(request):
    """Returns graph(s) per request

    Graphs can be specified by:
    Host - all services possessed by host
    Host & Service - service of host
    Group & Service - all instances of service in group
    """
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
    end = int(time.time())
    start = end - DAY

    if not(service):
        if host:
            service_list = servicelist_by_host(stat, host)
            service_list.sort(lambda x, y:  \
                cmp(x['service_description'], y['service_description']))
            for x in service_list:
                x['is_graphable'] = is_graphable(host, x)
                x['start'] = start
                x['end'] = end
                x['period'] = 'ajax'
        else:
            return HttpResponse('')
    else:
        if host:
            service_detail = servicedetail(stat, host, service)
            service_detail['is_graphable'] = is_graphable(host, service)
            service_detail['start'] = start
            service_detail['end'] = end
            service_detail['period'] = 'ajax'
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
                service['start'] = start
                service['end'] = end
                service['period'] = 'ajax'

    context_data = {
        'loaded_graphs': service_list,
    }
    c = Context(context_data)
    return HttpResponse(t.render(c))

def directurl(request, id):
    """Returns a saved page by id"""
    stat, obj = parse()
    loaded_graphs = []

    if id != None:
        content = pickle.loads(str(URL.objects.get(id=id)))
        for array in content:
            if len(array) == 4:
                host, service, start, end = array
                service_detail = servicedetail(stat, host, service)
                service_detail['is_graphable'] = True
                service_detail['start'] = start
                service_detail['end'] = end
                service_detail['period'] = 'zoomed'
                loaded_graphs.append(service_detail)
            elif len(array) == 2:
                host, service = array
                service_detail = servicedetail(stat, host, service)
                service_detail['is_graphable'] = False
                loaded_graphs.append(service_detail)
    
    return configurator(stat, obj, 'Saved URL #%s' % id,  \
            'Saved URL #%s' % id,loaded_graphs)

def directconfigurator(request):
    """Returns a blank configurator page"""
    stat, obj = parse()
    return configurator(stat, obj)

def configurator(stat, obj, htmltitle='Configurator',   \
                     pagetitle='Configurator', loaded_graphs=[]):
    """Returns a configurator page
    Loads specified graphs, sets specified htmltitle and pagetitle, and
    displays the configurator form
    """
    t = loader.get_template('configurator.html')
    context_data = {
        'loaded_graphs': loaded_graphs,
        'htmltitle': htmltitle,
        'pagetitle': pagetitle,
        'graphs': True,
    }
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def generatelink(request):
    """Add the current page configuration to db and return its row id"""
    if request.method == "POST":
        querydict = request.POST 
    else:
        querydict = request.GET

    digits = re.compile('(\d+)')
    graph_list = [graph for graph in querydict.iterlists()]

    def digitcmp(x,y): 
        xmatch = digits.search(x[0])
        ymatch = digits.search(y[0])
        # xmatch and ymatch SHOULD be valid, but just in case
        xrow = int(xmatch.group(0)) if xmatch else 1337
        yrow = int(ymatch.group(0)) if ymatch else 1337
        return cmp(xrow, yrow)

    graph_list.sort(digitcmp)
    content = pickle.dumps([graph[1] for graph in graph_list])

    hostname = 'http' + ('s' if request.is_secure() else '') + '://' +    \
                request.META['SERVER_NAME']

    try:
        id = URL.objects.get(content=content).id
    except Exception:
        link = URL(content=content)
        link.save()
        id = link.id
    return HttpResponse(json.dumps(hostname + '/railroad/c/' + str(id)))

def stripstate(state):
    """Strips names out of groups/hosts/services in state"""
    state['group'] = map(lambda x: x['alias'], state['group'])
    state['host'] = map(lambda x: x['host_name'], state['host'])
    state['service'] = list(    \
        set(map(lambda x: x['service_description'], state['service'])))
    state['service'].sort()
    return state

def selectgroup(state, group_name):
    """Update state per group selection (filter hosts by group membership and
    filter services by hosts in group)
    """
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
    """Update state per host selection (filter services by host)"""
    all_services = state['service']
    state['group'] = []
    state['host'] = []
    state['service'] = [service for service in all_services \
        if service['host_name'] == host]

def selectservice(state, service):
    """Update state per service selection (filter hosts and groups by
    possession of service)
    """
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
    """Return the new state of the configurator form"""
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
            map(lambda x: '%s%s' % (x[0].upper(), x[1:]), state['options'])
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

    state['options'] = map(lambda x: '%s%s' % (x[0].upper(), x[1:]),    \
                            state['options'])
    
    state['ready'] = False
    if host:
        state['ready'] = True
    elif service and group:
        state['ready'] = True

    return HttpResponse(json.dumps(stripstate(state)))

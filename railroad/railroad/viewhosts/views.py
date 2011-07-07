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
import math
import os
import sys
import re
import time
import pickle
import re
from unicodedata import normalize
import coil
import rrdtool

from django import forms
from django.conf import settings
from django.http import HttpResponse, HttpRequest, Http404
from django.template import Context, loader
from django.shortcuts import render_to_response

from nagcat import nagios_objects
from railroad.errors import RailroadError
from railroad.viewhosts.models import URL
from railroad.parserrd.views import get_data

DAY = 86400 # 1 Day in seconds

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
#    try:
#        staturl = urllib.urlopen('http://localhost:13337/status')
#        stat = pickle.loads(staturl.read())
#    except Exception:
    stat_path = '%sstatus.dat' % data_path
    stat = nagios_objects.ObjectParser(stat_path, ('service', 'host'))

#    try:
#        objurl = urllib.urlopen('http://localhost:13337/objects')
#        stat = pickle.loads(objurl.read())
#    except Exception:
    obj_path = '%sobjects.cache' % data_path 
    obj = nagios_objects.ObjectParser(obj_path, ('hostgroup'))
    # / in group names break urls, replace with - which are safer
    for group in obj['hostgroup']:
        group['alias'] = group['alias'].replace('/', '-')

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
    return [x['alias'] for x in views.grouplist(obj)]

def hostnames(stat):
    """Returns a list of host names"""
    return [x['host_name'] for x in hostlist(stat)]

def servicenames(stat):
    """Returns a list of service names"""
    return [x['service_description'] for x in servicelist(stat)]

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

def get_graphs(stat, obj, hosts='', groups='', services='', start=None, end=None):
    """Returns a list of services objects, marked graphable or not""" 
    groups = set([group.strip() for group in groups.split(',') if group.strip()])
    hosts = set([host.strip() for host in hosts.split(',') if host.strip()])
    services = set([service.strip() for service in services.split(',') if service.strip()])

    group_hosts = set() # Hosts under the given groups
    all_hosts = set()  # All hosts will contain all host names from host and group

    if not end:
        end = int(time.time())
    if not start:
        start = end - DAY

    if groups:
        for group in groups:
            group_hosts.update(set(hostnames_by_group(stat,obj,group)))
    all_hosts.update(hosts | group_hosts) if hosts | group_hosts else None
    service_list = [] # Will contain the service objects
    # Given hosts and no services, we want to get all services for those hosts.
    if all_hosts and not services:
        for host in all_hosts:
            for service in servicelist_by_host(stat,host):
                service_list.append(service)
    # Given no hosts and services, we want to get all hosts for those services.
    # Given hosts and services, we want to start by getting all of the hosts with the services listed, and then will later filter out the hosts we don't want
    if (not all_hosts and services) or (all_hosts and services):
        for service in services:
            for host in hostlist_by_service(stat,service):
                service_list.append(servicedetail(stat,host['host_name'],service))
    # Given hosts and services, we already have a list of all hosts for the listed services, we want to filter out hosts that weren't listed.
    if all_hosts and services:
        service_list = [service for service in service_list if (lambda x: x in all_hosts) (service['host_name'])]
    # Find out whether each service object is graphable or not
    for service in service_list:
        service['is_graphable'] = is_graphable(service['host_name'], service['service_description'])
        service['start']  = start
        service['end']    = end
        service['period'] = 'ajax'
        service['slug'] = slugify(service['host_name']+service['service_description'])
    return service_list

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

def error404(request):
    """Returns the 404 page"""
    t = loader.get_template('404.html')
    stat, obj = parse()
    context_data = {}
    context_data = add_hostlist(stat, obj, context_data)

    return HttpResponse(t.render(c))

def graphpage(request,host=None,service=None):
    """Returns a page of graphs matching specific filter criteria."""
    t = loader.get_template('graphpage.html')
    htmltitle = "Railroad Graphs"
    pagetitle = "Railroad Graphs"
    # fake up a query if we're using Django URL arguments
    query = request.GET.copy()
    if host:
        query['host'] = host
    if service:
        query['service'] = service
    if len(query):
        # if no box is checked, check them all
        if not (('a_red' in query) or ('a_yellow' in query)
                or ('a_green' in query)):
            query['a_red'] = True
            query['a_yellow'] = True
            query['a_green'] = True
        filterform = FilterForm(query)
    else:
        filterform = FilterForm()
    stat, obj = parse()
    loaded_graphs = []
    end = int(time.time())
    start = end - DAY
    loaded_graphs = servicelist_by_filters(stat,query)
    sortby = query.get('sortby','')
    revsort = bool(query.get('sortreverse',False))
    if sortby == 'rrd':
        keyfunc = sortkey_from_rrd
    else:
        keyfunc = lambda x: x['service_description']
    loaded_graphs.sort(key=keyfunc,reverse=revsort)
    for graph in loaded_graphs:
        graph['is_graphable'] = is_graphable(graph['host_name'],
                                             graph['service_description'])
        graph['start'] = start
        graph['end'] = end
        graph['period'] = 'ajax'

    context_data = {'getvars' : query,
                    'request' : request,
                    'filterform' : filterform,
                    'loaded_graphs' : loaded_graphs,
                    'htmltitle' : htmltitle,
                    'pagetitle' : pagetitle,
                    }
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))

def sortkey_from_rrd(service):
    """Generate a sort key for SERVICE from the latest minute of RRD values.

    Currently just returns the whole list of results, meaning that we effectively sort by first trend."""
    return fetch_current_rrd_data(service)[2][0]

def fetch_current_rrd_data(service,interval=60,aggregate='AVERAGE'):
    """Fetch the current data for SERVICE over INTERVAL aggregated by AGGREGATE."""
    rra_path = settings.RRA_PATH
    rrd = '%s%s/%s.rrd' % (rra_path, service['host_name'],
                           service['service_description'])
    if not os.path.exists(rrd):
        # there's no RRD file for state-only checks so return a dummy list
        end = int(time.time())
        start = end - interval
        return [(start,end,interval),
                ('dummy1','dummy2'),
                (0,0)]
    end = rrdtool.last(rrd)
    start = end - interval
    return rrdtool.fetch(rrd,'--start',str(start),'--end',str(end),aggregate)

def servicelist_by_filters(stat,filters={}):
    """Return a list of services from STAT that match FILTERS."""
    # by default, match everything
    svcs = servicelist(stat)
    # first, look at hostnames
    hnames = set(hostnames(stat))
    if filters.get('host',None):
        # try exact match first
        if filters['host'] in hnames:
            svcs = [ s for s in svcs if s['host_name'] == filters['host']]
        else:
            svcs = [ s for s in svcs if re.search(filters['host'],s['host_name']) ]
    if filters.get('service',None):
        # very unlikely that an exact match would also be a substring,
        # so don't bother trying that first
        svcs = [ s for s in svcs
                 if re.search(filters['service'],s['service_description']) ]
    if (('a_red' in filters) or ('a_yellow' in filters)
        or ('a_green' in filters)):
        alertlevels = set()
        if filters.get('a_red',False):
            alertlevels.add("2")
        if filters.get('a_yellow',False):
            alertlevels.add("1")
        if filters.get('a_green',False):
            alertlevels.add("0")
        svcs = [ s for s in svcs if s['current_state'] in alertlevels ]
    return svcs

sort_options = (
    ('svc','Service Name'),
    ('rrd','Latest RRD values'),
    )

class FilterForm(forms.Form):
    # The widget, attr is used to enable autocomplete on these text forms
    host = forms.CharField(required=False, widget = forms.TextInput(attrs = { "id": "host", "class": "autocomplete"}))
    service = forms.CharField(required=False, widget = forms.TextInput( attrs = { "id": "service", "class":"autocomplete"}))
    a_green = forms.BooleanField(required=False,initial=True,label="OKAY (green)")
    a_yellow = forms.BooleanField(required=False,initial=True,label="WARN (yellow)")
    a_red = forms.BooleanField(required=False,initial=True,label="CRITICAL (red)")
    sortreverse = forms.BooleanField(required=False,label="Reverse sort order")
    sortby = forms.ChoiceField(choices=sort_options,initial="svc",label="Sort results by")

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
 
    host_detail = hostdetail(stat, host)
    if(host_detail == None):
        raise Http404
    page_state = host_detail.get('current_state', '')

    return configurator(stat, obj,  \
        'Host Detail: %s' % host, host, loaded_graphs, page_state)

def service(request, host, service):
    """Returns a page showing service details of specified service of host"""
    t = loader.get_template('service.html')
    stat, obj = parse()
    service_detail = servicedetail(stat, host, service)
    host_detail = hostdetail(stat, host)

    if service_detail == None or host_detail == None:
        raise Http404

    plugin_output = service_detail.get('plugin_output', '')
    long_output = service_detail.get('long_plugin_output', '')

    service_state = service_detail.get('current_state', '')

    rra_path = settings.RRA_PATH
    coilfile = '%s%s/%s.coil' % (rra_path, host, service)

    coilstring = ''
    if os.path.exists(coilfile):
        coilstring = open(coilfile).read()
    
    time_intervals = get_time_intervals()
    context_data = {
        'host_name': host,
        'host_state': host_detail.get('current_state', ''),
        'service_name': service,
        'service_output': long_output,
        'plugin_output': plugin_output,
        'service_state': service_state,
        'coil' : coilstring,
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

    try:        
        host_list = hostlist_by_group(stat, obj, group)
    except Exception:
        raise Http404
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
    Group - All services of all hosts in the group
    Service - All hosts with the specified service(s)
    Host & Service - service of host
    Group & Service - all instances of service in group
    Host & Group & Service - All chosen services of all chosen hosts

    Graphs - A list of dictionaries containing host and service keys
    """

    stat,obj = parse()

    graphs = request.GET.get("graphs", None)
    if graphs:
        graphs = json.loads(graphs)
        service_list = [servicedetail(stat, g['host'], g['service']) for g in graphs]
        filter(None, service_list)

        for service in service_list:
            service['is_graphable'] = is_graphable(service['host_name'],
                    service['service_description'])
            service['slug'] = slugify(service['host_name'] +
                                      service['service_description'])
    else:
        groups = request.GET.get("group")
        hosts = request.GET.get("host")
        services = request.GET.get("service")

        service_list = get_graphs(stat, obj, hosts, groups, services)

    c = {'loaded_graphs': service_list}
    return render_to_response('graph.html', c)

def directurl(request, id):
    """Returns a saved page by id"""
    stat, obj = parse()
    loaded_graphs = []

    out_end = int(time.time())
    out_start = out_end - DAY

    if id != None:
        try:
            content = pickle.loads(str(URL.objects.get(id=id)))
        except Exception:
            raise Http404
        for array in content:
            if len(array) == 4:
                host, service, start, end = array
                service_detail = servicedetail(stat, host, service)
                service_detail['is_graphable'] = True
                if start == '-1' and end == '-1':
                    service_detail['start'] = out_start
                    service_detail['end'] = out_end
                    service_detail['period'] = 'ajax'
                else:
                    service_detail['start'] = start
                    service_detail['end'] = end
                    service_detail['period'] = 'zoomed'
                loaded_graphs.append(service_detail)
            elif len(array) == 2:
                host, service = array
                service_detail = servicedetail(stat, host, service)
                service_detail['is_graphable'] = False
                loaded_graphs.append(service_detail)
    
    return configurator(stat, obj, 'Saved Page',  \
            'Saved Page', loaded_graphs)

def directconfigurator(request):
    """Returns a blank configurator page"""
    stat, obj = parse()
    return configurator(stat, obj)

def hostconfigurator(request, hosts):
    """Returns a configurator page with graphs on it"""
    stat, obj = parse()
    service_list = get_graphs(stat, obj, hosts)
    return configurator(stat, obj, 'Configurator', 'Configurator', service_list)

def serviceconfigurator(request, service):
    """Returns a configurator page with graphs on it"""
    stat, obj = parse()
    service_list = get_graphs(stat, obj, "", "", service)
    return configurator(stat, obj, 'Configurator', 'Configurator', service_list)


def configurator(stat, obj, htmltitle='Configurator',            \
                     pagetitle='Configurator', loaded_graphs=[], \
                     page_state=''):
    """Returns a configurator page
    Loads specified graphs, sets specified htmltitle and pagetitle, and
    displays the configurator form
    """
    t = loader.get_template('configurator.html')
    context_data = {
        'loaded_graphs': loaded_graphs,
        'htmltitle': htmltitle,
        'pagetitle': pagetitle,
        'page_state': page_state,
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
    state = {
        'options': ['group', 'host', 'service'],
        'group': grouplist(obj),
        'host': hostlist(stat),
        'service': servicelist(stat)
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

def graphs(request):
    stat, obj = parse()

    graphs = request.GET.get('graphs', None)
    hosts = request.GET.get('host', '')
    services = request.GET.get('service', '')
    groups = request.GET.get('group', '')
    get_start = request.GET.get('start', None)
    get_end = request.GET.get('end', None)
    res = request.GET.get('res', None)

    if graphs:
        graphs = json.loads(graphs)
        service_objs = []
        for graph in graphs:
            so = servicedetail(stat, graph['host'], graph['service'])
            if not so:
                continue
            so['start'] = graph.get('start', get_start)
            so['end'] = graph.get('end', get_end)
            service_objs.append(so)
    else:
        service_objs = get_graphs(stat, obj, hosts, groups, services, get_start, get_end)

    HttpResponse(repr(service_objs))

    response = []

    for s in service_objs:
        host = s['host_name']
        service = s['service_description']
        start = s.get('start')
        end = s.get('end')

        one_response = {
            'host': host,
            'service': service,
            'current_time': time.strftime('%H:%M:%S %Z', time.gmtime()),
            'slug': slugify(host + service),
        }

        if is_graphable(host, service):
            one_response.update(get_data(host, service, start, end))

        response.append(one_response)

    return HttpResponse(json.dumps(response))

# From http://flask.pocoo.org/snippets/5/
_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')
def slugify(text, delim=u''):
    """
    Generates a slug that will only use ASCII, be all lowercase, have no
    spaces, and otherwise be nice for filenames, identifiers, and urls.
    """
    result = []
    for word in _punct_re.split(text.lower()):
        word = normalize('NFKD', unicode(word)).encode('ascii', 'ignore')
        if word:
            result.append(word)
    return unicode(delim.join(result))


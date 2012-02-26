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
import time
from unicodedata import normalize
from datetime import datetime
from fnmatch import fnmatch

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

def json_handle_datetime(obj):
    return time.mktime(obj.timetuple()) if isinstance(obj, datetime) else obj

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
                if type() == type(query) and 'trend' in val:
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
                    if type() == type(query) and 'trend' in val:
                        service['is_graphable'] = True
                        break
                service['is_graphable'] = False

        else:
            service['is_graphable'] = False


def parse():
    """
    Uses nagcat's nagios object parser to get host, service, group
    details.
    """
    data_path = settings.DATA_PATH
    stat_path = '{0}/status.dat'.format(data_path)
    stat = nagios_objects.ObjectParser(stat_path)

    obj_path = '%sobjects.cache' % data_path
    obj = nagios_objects.ObjectParser(obj_path, ('hostgroup'))

    # Convert unix times to python datetimes.

    SERVICE_DATE_OBJS = ['last_state_change', 'last_time_critical',
            'last_hard_state_change', 'last_update', 'last_time_ok',
            'last_check', 'next_check']
    for s in stat['service']:
        s['state_duration'] = (int(time.time()) -
            int(s['last_state_change']))
        for key in SERVICE_DATE_OBJS:
            s[key] = datetime.utcfromtimestamp(int(s[key]))

    DOWNTIME_DATE_OBJS = ['entry_time', 'start_time', 'end_time']
    if 'hostdowntime' in stat:
        for dt in stat['hostdowntime']:
            for key in DOWNTIME_DATE_OBJS:
                dt[key] = datetime.utcfromtimestamp(int(dt[key]))
    if 'servicedowntime' in stat:
        for dt in stat['servicedowntime']:
            for key in DOWNTIME_DATE_OBJS:
                dt[key] = datetime.utcfromtimestamp(int(dt[key]))

    # / in group names break urls, replace with - which are safer
    for group in obj['hostgroup']:
        group['alias'] = group['alias'].replace('/', '-')

    for service in stat['service']:
        # Django doesn't like variables that start with _.
        if '_TEST' in service:
            service['nagcat_template'] = service['_TEST'].split(';', 1)[-1]
        else:
            service['nagcat_template'] = ''

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
    """Returns a list of groups with the specified name."""
    group_list = grouplist(obj)
    return filter(lambda g: fnmatch(g['alias'].lower(), group_name.lower()),
        group_list)


def hostdetail(stat, host_name):
    """Returns a list of hosts that match the give host pattern."""
    host_list = hostlist(stat)
    for host in host_list:
        if host['host_name'] == host_name:
            return host


def servicelist_by_description(stat, service_name):
    """Returns a list of service objects with the specified name"""
    all_services = servicelist(stat)
    return filter(
        lambda s: fnmatch(s['service_description'].lower(), service_name.lower()),
        servicelist(stat))


def servicedetail(stat, host, service_name):
    """
    Returns a list of service objects that match the given host and service
    name patterns.
    """
    services_matching = servicelist_by_description(stat, service_name)
    return filter(lambda s: fnmatch(s['host_name'].lower(), host.lower()),
        services_matching)


def hostlist_by_group(stat, obj, group_name):
    """Returns a list of hosts with the specified group"""
    groups = groupdetail(obj, group_name)
    all_hosts = hostlist(stat)
    target = [t for g in groups for t in g['members'].split(',')]
    return filter(lambda h: h['host_name'] in target, all_hosts)


def hostnames_by_group(stat, obj, group_name):
    """Returns a list of host names with the specified group"""
    groups = groupdetail(obj, group_name)
    return [h for g in groups for h in g['members'].split(',')]


def hostlist_by_service(stat, service):
    """Returns a list of hosts possessing the specified service"""
    all_services = servicelist(stat)
    filtered = []
    for s in all_services:
        if fnmatch(s['service_description'].lower(), service.lower()):
            filtered.append(s)
        elif 'service_alias' in s and fnmatch(s['service_alias'], service.lower()):
            filtered.append(s)
    return filtered


def hostnames_by_service(stat, service):
    """Returns a list of hosts (names) possessing the specified service"""
    all_services = servicelist(stat)
    return filter(
        lambda s: fnmatch(s['service_description'].lower(), service.lower()),
        all_services)


def servicelist_by_host(stat, host):
    """Returns a list of services possessed by the specified host"""
    return filter(lambda h:
            fnmatch(h['host_name'].lower(), host.lower()),
            servicelist(stat))


def servicenames_by_host(stat, host):
    """Returns a list of services (names) possessed by the specified host"""
    all_services = servicelist(stat)
    return [service['service_description'] for service in all_services  \
                                if service['host_name'].lower() == host.lower()]


def get_graphs(stat, obj, hosts='', groups='', services='', tests='',
               start=None, end=None):
    """Returns a list of services objects, marked graphable or not"""
    groups = groups or ''
    groups = [g.strip() for g in groups.split(',')]
    groups = set(filter(lambda g: bool(g), groups))

    hosts = hosts or ''
    hosts = [h.strip() for h in hosts.split(',')]
    hosts = set(filter(lambda h: bool(h), hosts))

    services = services or ''
    services = [s.strip() for s in services.split(',')]
    services = set(filter(lambda s: bool(s), services))

    tests = tests or ''
    tests = [t.strip() for t in tests.split(',')]
    tests = set(filter(lambda t: bool(t), tests))

    group_hosts = set() # Hosts under the given groups
    all_hosts = set() # Will contain all host names from host and group

    if not end:
        end = int(time.time())
    if not start:
        start = end - DAY

    if groups:
        for group in groups:
            group_hosts.update(set(hostnames_by_group(stat, obj, group)))

    if hosts or group_hosts:
        all_hosts.update(hosts | group_hosts)
    service_list = [] # Will contain the service objects

    # Given hosts and no services, we want to get all services for those hosts.
    if all_hosts and not services:
        for host in all_hosts:
            for service in servicelist_by_host(stat, host):
                service_list.append(service)

    # Given no hosts and services, we want to get all hosts for those services.
    # Given hosts and services, we want to start by getting all of the hosts
    # with the services listed, and then will later filter out the hosts we
    # don't want
    for service in services:
        for host in hostlist_by_service(stat, service):
            service_list += servicedetail(stat, host['host_name'],
                    host['service_description'])

    # Given hosts and services, we already have a list of all hosts for the
    # listed services, we want to filter out hosts that weren't listed.
    if all_hosts and services:
        new_services = []
        for s in service_list:
            for h in all_hosts:
                if fnmatch(s['host_name'], h):
                    new_services.append(s)
                    break
        service_list = new_services

    if tests:
        service_list = filter(
            lambda x: x.get('nagcat_template', None) in tests,
            service_list)

    # Find out whether each service object is graphable or not
    for service in service_list:
        service['is_graphable'] = is_graphable(service['host_name'],
                                               service['service_description'])
        service['start'] = start
        service['end'] = end
        service['period'] = 'ajax'
        service['slug'] = slugify(service['host_name'] +
                service['service_description'])

    return service_list


def get_time_intervals():
    """Returns a list of (start, end) intervals for day, week, month, year"""
    #            day  , week  , month  , year
    intervals = [86400, 604800, 2592000, 31104000]
    times = ['day', 'week', 'month', 'year']
    end = int(time.time())
    return zip(times, [[end - interval, end] for interval in intervals])


def add_hostlist(stat, obj, c):
    # TODO: This should probably just be a class that wraps Context, as we
    # will have to include this on each and every page

    """Returns the given context with the sidebar filled in"""
    groups = grouplist(obj)
    groups.sort(lambda x, y: cmp(x['alias'], y['alias']))
    hosts = hostlist(stat)
    sidebar = []
    for group in groups:
        group_name = group['alias']
        addinghosts = group.get('members', '').split(',')
        hosts_of_group = []
        for host in hosts:
            if host['host_name'] in addinghosts:
                hosts_of_group.append(host)
                host['has_group'] = True
        hosts_of_group.sort(lambda x, y: cmp(x['host_name'], y['host_name']))
        sidebar.append((group_name, hosts_of_group))
    no_group = [x for x in hosts if 'has_group' not in x]
    if len(no_group):
        sidebar.append(('(no group)', no_group))
    c['sidebar'] = sidebar
    return c


def index(request):
    """Returns the index page"""
    t = loader.get_template('index.html')
    stat, obj = parse()

    services = stat['service']
    hosts = stat['host']

    host_status = {}
    for h in hosts:
        host_status[h['host_name']] = h['current_state']

    for s in services:
        s['host_state'] = host_status[s['host_name']]

    context_data = {'services': services}
    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))


def graphpage(request, host=None, service=None):
    """Returns a page of graphs matching specific filter criteria."""

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
    loaded_graphs = servicelist_by_filters(stat, query)

    for graph in loaded_graphs:
        graph['is_graphable'] = is_graphable(graph['host_name'],
                                             graph['service_description'])
        graph['start'] = start
        graph['end'] = end
        graph['period'] = 'ajax'

    context_data = {'getvars': query,
                    'request': request,
                    'filterform': filterform,
                    'loaded_graphs': loaded_graphs,
                    'htmltitle': htmltitle,
                    'pagetitle': pagetitle,
                    }
    context_data = add_hostlist(stat, obj, context_data)
    return render_to_response('graphpage.html', context_data)


def sortkey_from_rrd(service):
    """
    Generate a sort key for SERVICE from the latest minute of RRD values.

    Currently just returns the whole list of results, meaning that we
    effectively sort by first trend.
    """
    return fetch_current_rrd_data(service)[2][0]


def fetch_current_rrd_data(service, interval=60, aggregate='AVERAGE'):
    """
    Fetch the current data for SERVICE over INTERVAL aggregated by AGGREGATE.
    """
    rra_path = settings.RRA_PATH
    rrd = '%s%s/%s.rrd' % (rra_path, service['host_name'],
                           service['service_description'])
    if not os.path.exists(rrd):
        # there's no RRD file for state-only checks so return a dummy list
        end = int(time.time())
        start = end - interval
        return [(start, end, interval),
                ('dummy1', 'dummy2'),
                (0, 0)]
    end = rrdtool.last(rrd)
    start = end - interval
    return rrdtool.fetch(rrd, '--start', str(start),
                              '--end', str(end), aggregate)


def host(request, host):
    """Returns a page showing all services of the specified host"""
    loaded_graphs = []
    stat, obj = parse()
    if host != None:
        end = int(time.time())
        start = end - DAY
        loaded_graphs = servicelist_by_host(stat, host)
        loaded_graphs.sort(lambda x, y: cmp(x['service_description'],    \
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

    return configurator(request, stat, obj,
        'Host Detail: %s' % host, host, loaded_graphs, page_state)

def service(request, host, service):
    """Returns a page showing service details of specified service of host"""
    t = loader.get_template('service.html')
    stat, obj = parse()
    # We assume there are exactly one of these, so grab the first element.
    service_detail = servicedetail(stat, host, service)[0]
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

    graphs = []
    for x in time_intervals:
        temp_dict = {
            "host": host,
            "service":  service,
            "end" : x[1][0],
            "start": x[1][1],
            "uniq": time_intervals.index(x),
        }
        graphs.append(temp_dict)

    context_data = {
        'host_name': host,
        'json_services': json.dumps({'host': host, 'service': service}),
        'slug': slugify(host + service),
        'host_state': host_detail.get('current_state', ''),
        'service_name': service,
        'service_output': long_output,
        'plugin_output': plugin_output,
        'service_state': service_state,
        'coil': coilstring,
        'graphable': is_graphable(host, service),
        'time_intervals': time_intervals}

    context_data = add_hostlist(stat, obj, context_data)
    c = Context(context_data)
    return HttpResponse(t.render(c))


def group(request, group):
    """Returns a page showing all hosts/services of the specified group"""
    stat, obj = parse()
    service_dict = {}

    host_list = hostlist_by_group(stat, obj, group)
    if not host_list:
        raise Http404

    host_names = map(lambda x: x['host_name'], host_list)
    services = []
    for host in host_names:
        services += servicelist_by_host(stat, host)

    services.sort(key=lambda x: x['service_description'])
    host_list.sort(key=lambda x: x['host_name'])

    # Uniquify the service names
    service_dict = {}
    for s in services:
        key = s['service_description']
        service_dict[key] = s

    services = service_dict.values()

    end = int(time.time())
    start = end - DAY
    context_data = {
        'group_name': group,
        'hosts': host_list,
        'services': services,
        'time_interval': [start, end]}

    context_data = add_hostlist(stat, obj, context_data)
    return render_to_response('group.html', context_data)


def form(request):
    """Returns a form for choosing group/host/service"""
    t = loader.get_template('form.html')
    stat, obj = parse()
    group_list = grouplist(obj)
    group_list.sort(lambda x, y: cmp(x['alias'], y['alias']))
    host_list = hostlist(stat)
    host_list.sort(lambda x, y: cmp(x['host_name'], y['host_name']))
    service_list = list(set(map(lambda x: x['service_description'], \
                                            servicelist(stat))))
    service_list.sort()

    end = int(time.time())
    start = end - DAY
    context_data = {
        'group_list': group_list,
        'host_list': host_list,
        'service_list': service_list,
        'time_interval': [start, end]}
    c = Context(context_data)
    return HttpResponse(t.render(c))

def real_service_page_meta(request):
    source = request.POST if request.POST else request.GET
    host = source.get('host', '')
    service = source.get('service', '')
    time_intervals = get_time_intervals()
    graphs = []
    for time in time_intervals:
        so = {
            'host': host,
            'service': service,
            'slug': slugify(host + service),
            'start': time[1][0],
            'end': time[1][1],
            'title': time[0],
            'uniq': time_intervals.index(time)
        }
        html = render_to_response('service_graph.html', so).content
        so['html'] = html
        graphs.append(so)
    return graphs

def service_page_meta(request):
    return HttpResponse(json.dumps(real_service_page_meta(request)))

def real_meta(hosts='', services='', groups='', tests=''):
    stat, obj = parse()

    response = []
    graph_template = loader.get_template('graph.html')

    for graph in get_graphs(stat, obj, hosts, groups, services, tests):

        so = {
            'host': graph['host_name'],
            'service': graph['service_description'],
            'slug': slugify(graph['host_name'] + graph['service_description']),
            'isGraphable': graph['is_graphable'],
            'html': render_to_response('graph.html', graph).content,
            'state': graph['current_state'],
            'duration': graph['state_duration'],
            'nagcat_template': graph['nagcat_template'],
        }

        if so['isGraphable']:
            so.update({
                'start': graph['start'],
                'end': graph['end'],
            })

        response.append(so)

    return response


def meta(request):
    """
    Get a bunch of json metadata for a request.
    """
    print >> sys.stderr, "This is a a test"
    sys.stderr.flush()

    stat, obj = parse()
    source = request.POST if request.POST else request.GET

    groups = source.get('group', source.get('groups', ''))
    hosts = source.get('host', source.get('hosts', ''))
    services = source.get('service', source.get('services', ''))

    return HttpResponse(json.dumps(real_meta(hosts, services, groups)),
            content_type='application/json')


def customgraph(request):
    """Returns graph(s) per request

    Graphs can be specified by:
    Host - all services possessed by host
    Group - All services of all hosts in the group
    Service - All hosts with the specified service(s)
    Host & Service - service of host
    Group & Service - all instances of service in group
    Host & Group & Service - All chosen services of all chosen hosts
    uniq - A unique identifier the client may set for this graph.

    Graphs - A list of dictionaries containing host and service keys
    """

    source = request.POST if request.POST else request.GET
    stat, obj = parse()

    graphs = source.get("graphs", None)
    if graphs:
        graphs = json.loads(graphs)
        service_list = []
        for graph in graphs:
            s = servicedetail(stat, graph['host'], graph['service'])
            if not s:
                continue
            s = s[0]
            s['is_graphable'] = is_graphable(s['host_name'],
                    s['service_description'])
            s['slug'] = slugify(s['host_name'] + s['service_description'])
            if 'uniq' in graph:
                s['uniq'] = graph['uniq']
            service_list.append(s)
    else:
        groups = source.get("group")
        hosts = source.get("host")
        services = source.get("service")

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
                service_detail = servicedetail(stat, host, service)[0]
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
                service_detail = servicedetail(stat, host, service)[0]
                service_detail['is_graphable'] = False
                loaded_graphs.append(service_detail)

    return configurator(reuest, stat, obj, 'Saved Page',
            'Saved Page', loaded_graphs)


def directconfigurator(request):
    """Returns a configurator page, optionall populated from GET."""
    stat, obj = parse()

    query = {
        'hosts': request.GET.get('hosts', request.GET.get('host', '')),
        'services': request.GET.get('services', request.GET.get('service', '')),
        'groups': request.GET.get('group', request.GET.get('groups', '')),
        'tests': request.GET.get('tests', request.GET.get('test', '')),
    }

    service_list = real_meta(**query)

    return configurator(request, stat, obj, graphs=service_list)


def hostconfigurator(request, hosts):
    """Returns a configurator page with graphs on it"""
    stat, obj = parse()
    service_list = real_meta(hosts)
    return configurator(request, stat, obj, graphs=service_list)


def serviceconfigurator(request, service):
    """Returns a configurator page with graphs on it"""
    stat, obj = parse()
    service_list = real_meta(services=service)
    return configurator(request, stat, obj, graphs=service_list)


def configurator(request, stat, obj, htmltitle='Configurator',
        pagetitle='Configurator', graphs=[], permalink=False, link=''):
    """Returns a configurator page
    Loads specified graphs, sets specified htmltitle and pagetitle, and
    displays the configurator form
    """
    context_data = {
        'json_services': json.dumps(graphs, default=json_handle_datetime),
        'htmltitle': htmltitle,
        'pagetitle': pagetitle,
        'permalink': permalink,
        'link' : link,
    }
    if 'REMOTE_USER' in request.META and request.META['REMOTE_USER']:
        context_data['remoteuserid'] = request.META['REMOTE_USER']
    else:
        context_data['remoteuserid'] = 'anonymous railroad user'

    context_data = add_hostlist(stat, obj, context_data)
    return render_to_response('configurator.html', context_data);


def generatelink(request):
    """Add the current page configuration to db and return its row id"""
    if request.method == "POST":
        querydict = request.POST
    else:
        querydict = request.GET

    digits = re.compile('(\d+)')
    graph_list = [graph for graph in querydict.iterlists()]

    def digitcmp(x, y):
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
    stat, obj = parse()
    state = {
        'options': ['group', 'host', 'service'],
        'group': grouplist(obj),
        'host': hostlist(stat),
        'service': servicelist(stat)}

    if (not(querydict)):
        state['options'] =  \
            map(lambda x: '%s%s' % (x[0].upper(), x[1:]), state['options'])

    format = [('type0', 'value0'), ('type1', 'value1'), ('type2', 'value2')]
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

    source = request.POST if request.POST else request.GET

    graphs = source.get('graphs', source.get('graph', None))
    hosts = source.get('hosts', source.get('host', ''))
    services = source.get('services', source.get('service', ''))
    groups = source.get('groups', source.get('group', ''))
    get_start = source.get('start', None)
    get_end = source.get('end', None)
    res = source.get('res', None)
    uniq = source.get('uniq', None)

    if graphs:
        graphs = json.loads(graphs)
        service_objs = []
        for graph in graphs:
            if not graph:
                continue
            sos = servicedetail(stat, graph['host'], graph['service'])
            if not sos:
                continue
            sos = sos[0]
            for so in sos:
                so = so.copy()
                so['start'] = graph.get('start', get_start)
                so['end'] = graph.get('end', get_end)
                if 'uniq' in graph:
                    so['uniq'] = graph['uniq']
                service_objs.append(so)
    else:
        service_objs = get_graphs(stat, obj, hosts, groups, services,
                get_start, get_end)

    response = []

    for s in service_objs:
        host = s['host_name']
        service = s['service_description']
        start = s['start']
        end = s['end']

        one_response = {
            'host': host,
            'service': service,
            'current_time': time.strftime('%H:%M:%S %Z', time.gmtime()),
            'slug': slugify(host + service),
        }

        if 'uniq' in s:
            one_response['uniq'] = s['uniq']

        if is_graphable(host, service):
            one_response.update(get_data(host, service, start, end))

        response.append(one_response)

    response.sort(key=lambda r: r['service'])

    return HttpResponse(json.dumps(response), content_type="application/json")


def slugify(text, delim=u''):
    """
    Generates a slug that will only use ASCII, be all lowercase, have no
    spaces, and otherwise be nice for filenames, identifiers, and urls.

    From http://flask.pocoo.org/snippets/5/
    """
    result = []
    splits = re.split(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+', text.lower())
    for word in splits:
        word = normalize('NFKD', unicode(word)).encode('ascii', 'ignore')
        if word:
            result.append(word)
    return unicode(delim.join(result))


def parse_comment(comment):
    """Parses the real comment, and an expr and key from a nagnet comment."""
    comment, key, expr = (re.match(
        r'(.*?)(?: key:([A-Za-z0-9\-_]*))?(?: expr:(.*))?$',
        comment).groups())

    return comment, key, expr


def downtime(request):
    """List downtime."""
    stat, obj = parse()

    downtime = {}
    nag_dts = []
    if 'servicedowntime' in stat:
        nag_dts += stat['servicedowntime']
    if 'hostdowntime' in stat:
        nag_dts += stat['hostdowntime']

    for dt in nag_dts:
        dt['comment'], dt['key'], dt['expr'] = parse_comment(dt['comment'])

        if dt['key'] in downtime:
            downtime[dt['key']]['hosts_services'].append({
                'host': dt['host_name'],
                'service': dt['service_description']
            })
            downtime[dt['key']]['count'] += 1
        else:
            if 'service_description' in dt:
                hs = {
                    'host': dt['host_name'],
                    'service': dt['service_description'],
                }
            else:
                hs = {
                    'host': dt['host_name'],
                    'service': 'All services',
                }

            downtime[dt['key']] = {
                'hosts_services': [hs],
                'comment': dt['comment'],
                'expr': dt['expr'],
                'key': dt['key'],
                'author': dt['author'],
                'entry_time': dt['entry_time'],
                'start_time': dt['start_time'],
                'end_time': dt['end_time'],
                'count': 1,
            }

    c = {
        'downtime': downtime.values(),
        'json_downtime': json.dumps(downtime.values(),
            default=json_handle_datetime),
    }
    add_hostlist(stat, obj, c)

    return render_to_response('downtime.html', c)

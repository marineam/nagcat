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

from django.conf import settings
from django.http import HttpResponse
from railroad.errors import RailroadError

import rrdtool, json, os, coil, types, time

def sigfigs(float):
    desired_sigfigs = 3
    powers = range(desired_sigfigs)
    power = 0
    while power < powers:
        if float / pow(10,power) < 1:
            break
        power += 1

    if power == 3:
        return int(float)
    else:
        return round(float, desired_sigfigs - power)

def labelize(data, index, base, unit):
    statistics = data[index]['statistics']
    return ' (min: ' + str(sigfigs(statistics['min'] / base)) + unit \
        + ', max: ' + str(sigfigs(statistics['max'] / base)) + unit  \
        + ', avg: ' + str(sigfigs(statistics['avg'] / base)) + unit  \
        + ')'

def index(request, host, service, start, end, resolution='150'):
    rra_path = settings.RRA_PATH
    rrd = rra_path + host + '/' + service + '.rrd'
    coilfile = rra_path + host + '/' + service + '.coil'
    railroad_conf = 'railroad_conf'
    statistics = 'statistics'
    trend_attributes = ['color','stack','scale','display']

    DEFAULT_MIN = 99999999999999999999999


    # calculate custom resolution
    resolution = (int(end) - int(start)) / int(resolution)

    # rrdtool hates unicode strings, and Django gives us one,
    # so convert to ascii
    rrdslice = rrdtool.fetch(str(rrd),
                '--start', str(start),
                '--end', str(end),
                '--resolution', str(resolution),
                'AVERAGE')

    time_struct = time.gmtime()
    current_time = ':'.join([str(time_struct.tm_hour),  \
                             str(time_struct.tm_min),   \
                             str(time_struct.tm_sec) + ' UTC'])

    # Parse the data
    start,end,res = rrdslice[0]

    # Multiply by 1000 to convert to JS timestamp (millisecond resolution)
    res *= 1000

    coilstring = open(coilfile).read()
    coilstruct = coil.parse(coilstring)

    query = coilstruct.get('query',{})

    if not(query):
        raise RailroadError("OMG PONIES! query doesn't exist in coil file")

    graph_options = {
        'xaxis': {
            'mode': 'time', 
            'min': 1000 * int(start), 
            'max': 1000 * int(end)}, 
        'yaxis': {}, 
        'legend': {'position': 'nw'}, 
        'selection': {'mode': 'x'},
        'pan': {'interactive': True},
        'grid': {}
    }

    root_trend = coilstruct.get('trend',{})
    all_labels = rrdslice[1]
    labels = []

    root_label = None
    if root_trend:
        root_label = root_trend.get('label', None)
        if not(root_label):
            root_label = coilstruct.get('label', None)

    compound = query.get('type') == 'compound'

    if compound:
        for key in query.keys():
            val = query.get(key)
            if isinstance(val, coil.struct.Struct):
                trend = val.get('trend', None)
                if trend and trend.get('type', None):
                    label = trend.get('label', None)
                    if not(label):
                        label = key
                    labels.append((key,label))


    if 'query' in all_labels:
        trend = query.get('trend', None)
        if trend:
            query_label = trend.get('label', None)
            if not(query_label):
                query_label = root_label
            labels.append(('query', query_label if query_label else 'Result'))
        

    if '_result' in all_labels:
        labels.append(('_result', root_label if root_label else 'Result'))

    length = len(labels)
        
    indices = range(length)
    dataset = {}


    # flot_data and flot_data are of the format
    # [ { label: "Foo", data: [ [10, 1], [17, -14], [30, 5] ] },
    #   { label: "Bar", data: [ [11, 13], [19, 11], [30, -7] ] } ]
    # See Flot Reference (http://flot.googlecode.com/svn/trunk/API.txt)
    flot_data = [{'label': label[1], railroad_conf: {}, 'data': []}    \
                    for label in labels]

    labels = map(lambda x: x[0], labels)
    state_data = []
    
    # Reading graph options
    for index in indices:
        key = labels[index]
        trend = query.get(key,{}).get('trend',{})
        if not(trend):
            continue

        trend_settings = {}
        for var in trend_attributes: 
            trend_settings[var] = trend.get(var,'')

        if trend_settings['display']:
            flot_data[index]['lines'] =     \
                {'fill': 0.5 if trend_settings['display'] == 'area' else 0}

        if trend_settings['scale']:
            flot_data[index][railroad_conf]['scale'] = trend_settings['scale']
        else:
            flot_data[index][railroad_conf]['scale'] = 1

        if trend_settings['color']:
            flot_data[index]['color'] = trend_settings['color']

        if trend_settings['stack']:
            flot_data[index]['stack'] = True
            if index > 0:
                flot_data[index-1]['stack'] = True

    # See above
    x = start * 1000

    transform = [all_labels.index(z) for z in labels]
    stateIndex = all_labels.index('_state')

    datapoints = zip(all_labels,rrdslice[2][0])
    for index in indices:
        label,data = datapoints[transform[index]]

        flot_data[index][statistics] = {}
        flot_data[index][statistics]['num'] = 0
        flot_data[index][statistics]['sum'] = 0
        flot_data[index][statistics]['max'] = 0
        flot_data[index][statistics]['min'] = DEFAULT_MIN
        flot_data[index][railroad_conf]['scale'] = 1
        if data:
            flot_data[index][statistics]['max'] =                     \
                flot_data[index][statistics]['min'] =                 \
                    data * flot_data[index][railroad_conf]['scale']


    for tuple in rrdslice[2]:
        datapoints = zip(all_labels,tuple)
    
        label,data = datapoints[stateIndex]
        state_data.append([x,data])

        for index in indices:
            label,data = datapoints[transform[index]]

            if data != None:
                flot_data[index][statistics]['num'] += 1
                data *= flot_data[index][railroad_conf]['scale']
                flot_data[index][statistics]['sum'] += data
                if data > flot_data[index][statistics]['max']:
                    flot_data[index][statistics]['max'] = data
                if data < flot_data[index][statistics]['min']:
                    flot_data[index][statistics]['min'] = data

            flot_data[index]['data'].append([x,data])
    
        x += res

    empty_graph = True
    for index in indices:
        if flot_data[index][statistics]['num']:
            empty_graph = False

    base = 1000
    max = 100

    if length > 0:
        value = query.get(labels[0],{}).get('trend',{}).get('base','')
        if value:
            base = int(value)

        max = flot_data[0][statistics]['max']

        for index in indices:
            if flot_data[index][statistics]['num'] > 0:
                flot_data[index][statistics]['avg'] =           \
                    flot_data[index][statistics]['sum']         \
                        / flot_data[index][statistics]['num']
                if flot_data[index][statistics]['max'] > max:
                    max = flot_data[index][statistics]['max']

        bases = ['', 'K', 'M', 'G', 'T']
        for interval in range(len(bases)):
            if(max / (pow(base, interval)) <= base):
                break

        final_base = pow(base, interval)
        unit = bases[interval]

        for index in indices:
            if flot_data[index][statistics]['num'] > 0:
                flot_data[index]['label'] +=    \
                        labelize(flot_data, index, final_base, unit)
            else:
                flot_data[index]['label'] = flot_data[index]['label']       \
                    + ' (min: ' + 'N/A' \
                    + ', max: ' + 'N/A' \
                    + ', avg: ' + 'N/A' \
                    + ')'
                

    graph_options['yaxis']['max'] = max * 1.1 + 1

    if root_trend:
        axis_max = root_trend.get('axis_max','')
        if axis_max and graph_options['yaxis']['max'] < axis_max:
            graph_options['yaxis']['max'] = axis_max * 1.1 + 1
    
    fill = graph_options['yaxis']['max']

    if root_trend:
        axis_label = root_trend.get('axis_label','')
        if axis_label:
            graph_options['yaxis']['label'] = axis_label
        
    for index in indices:
        del(flot_data[index][railroad_conf])

    colors = ['#BBFFBB','#FFFFBB','#FFBBBB','#C0C0C0']
    markings = []
    state = state_data[0][1]
    if type(state) == types.FloatType:
        state = int(state) if float.is_integer(state) else 3
        markings.append({'xaxis': {'from': state_data[0][0]},   \
                            'color': colors[state]})
    for x,y in state_data:
        if type(y) == types.FloatType:
            y = int(y) if float.is_integer(y) else 3
        if y != state:
            if type(state) == types.IntType:
                markings[-1]['xaxis']['to'] = x
            state = y
            if type(state) == types.IntType:
                markings.append({'xaxis': {'from': x}, 'color': colors[state]})
    if type(state) == types.FloatType:
        markings[-1]['xaxis']['to'] = state_data[-1][0]

    empty_graph = empty_graph and (not(len(markings)))

    graph_options['grid']['markings'] = markings
    # Pass state, BUT DONT DRAW!! this is so taht graphs with ONLY state
    # still draw (otherwise they don't get axes, ticks, etc)
    flot_data.append({'data': state_data, 'lines': {'show': False}})

    result = {'options': graph_options, 'data': flot_data, 'base': base, 'empty': empty_graph, 'current_time': current_time}

    return HttpResponse(json.dumps(result))

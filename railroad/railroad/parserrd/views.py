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

from railroad.pathsettings import rra_path

import rrdtool, json, os, coil, types
from django.http import HttpResponse

def index(request, host, data, start, end, resolution='150'):
    global rra_path
    rrd = rra_path + host + '/' + data + '.rrd'
    coilfile = rra_path + host + '/' + data + '.coil'
    railroad_conf = 'railroad_conf'
    statistics = 'statistics'
    trend_settings = ['color','stack','scale','display']


    # calculate custom resolution
    resolution = (int(end) - int(start)) / int(resolution)

    # rrdtool hates unicode strings, and Django gives us one,
    # so convert to ascii
    rrdslice = rrdtool.fetch(str(rrd),
                '--start', str(start),
                '--end', str(end),
                '--resolution', str(resolution),
                'AVERAGE')

    # Parse the data
    start,end,res = rrdslice[0]

    # Multiply by 1000 to convert to JS timestamp (millisecond resolution)
    res *= 1000

    coilstring = open(coilfile).read()
    coilstruct = coil.parse(coilstring)

    query = coilstruct.get('query',{})

    if not(query):
        return HttpResponse("OMG PONIES! query doesn't exist in coil file")

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

    graph_trend = coilstruct.get('trend',{})


    allLabels = rrdslice[1]

    labels = []

    for key in query.keys():
        val = query.get(key)
        if type(val) == type(query) and val.has_key('trend'):
            labels.append(key)

    length = len(labels)
        
    indices = range(length)
    dataset = {}


    # flot_data and flot_data are of the format
    # [ { label: "Foo", data: [ [10, 1], [17, -14], [30, 5] ] },
    #   { label: "Bar", data: [ [11, 13], [19, 11], [30, -7] ] } ]
    # See Flot Reference (http://flot.googlecode.com/svn/trunk/API.txt)
    flot_data = [{'label': label, railroad_conf: {}, 'data': []}    \
                    for label in labels]
    state_data = []
    
    # Reading graph options
    for index in indices:
        key = labels[index]
        trend = query.get(key,{}).get('trend',{})
        if not(trend):
            continue

        settings = {}
        for var in trend_settings: 
            settings[var] = trend.get(var,'')

        if settings['display']:
            flot_data[index]['lines'] =     \
                {'fill': 0.5 if settings['display'] == 'area' else 0}

        if settings['scale']:
            flot_data[index][railroad_conf]['scale'] = settings['scale']
        else:
            flot_data[index][railroad_conf]['scale'] = 1

        if settings['color']:
            flot_data[index]['color'] = settings['color']

        if settings['stack']:
            flot_data[index]['stack'] = True
            if index > 0:
                flot_data[index-1]['stack'] = True

    # See above
    x = start * 1000

    transform = [allLabels.index(z) for z in labels]
    stateIndex = allLabels.index('_state')

    datapoints = zip(allLabels,rrdslice[2][0])
    for index in indices:
        label,data = datapoints[transform[index]]

        flot_data[index][statistics] = {}
        flot_data[index][statistics]['num'] = 0
        flot_data[index][statistics]['sum'] = 0
        flot_data[index][statistics]['max'] = 0
        flot_data[index][statistics]['min'] = 99999999999999999999999
        if data:
            flot_data[index][statistics]['max'] =                     \
                flot_data[index][statistics]['min'] =                 \
                    data * flot_data[index][railroad_conf]['scale']


    for tuple in rrdslice[2]:
        datapoints = zip(allLabels,tuple)
    
        label,data = datapoints[stateIndex]
        state_data.append([x,data])

        for index in indices:
            label,data = datapoints[transform[index]]

            flot_data[index][statistics]['num'] += 1
            if data:
                data *= flot_data[index][railroad_conf]['scale']
                flot_data[index][statistics]['sum'] += data
                if data > flot_data[index][statistics]['max']:
                    flot_data[index][statistics]['max'] = data
                if data < flot_data[index][statistics]['min']:
                    flot_data[index][statistics]['min'] = data

            flot_data[index]['data'].append([x,data])
    
        x += res

        #[[x,y * value] for x,y in d['data']]

    base = 1000
    max = 100

    if length > 0:
        value = query.get(labels[0],{}).get('trend',{}).get('base','')
        if value:
            base = int(value)

        max = flot_data[0][statistics]['max']
        for index in indices:
            flot_data[index][statistics]['avg'] =           \
                flot_data[index][statistics]['sum']         \
                    / flot_data[index][statistics]['num']
            if flot_data[index][statistics]['max'] > max:
                max = flot_data[index][statistics]['max']
            if flot_data[index][statistics]['max'] > 0:
                flot_data[index]['label'] = flot_data[index]['label']       \
                    + ' (min: ' + str(flot_data[index][statistics]['min'])  \
                    + ', max: ' + str(flot_data[index][statistics]['max'])  \
                    + ', avg: ' + str(flot_data[index][statistics]['avg'])  \
                    + ')'

    graph_options['yaxis']['max'] = max * 1.1

    if graph_trend:
        axis_max = graph_trend.get('axis_max','')
        if axis_max:
            graph_options['yaxis']['max'] = axis_max * 1.1
    
    fill = graph_options['yaxis']['max']

    if graph_trend:
        axis_label = graph_trend.get('axis_label','')
        if axis_label:
            graph_options['yaxis']['label'] = axis_label
        
    for index in indices:
        del(flot_data[index][railroad_conf])

    #flot_data = []
    colors = ['#33FF00','#FFFF00','#FF0000','#BEBEBE']
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

    graph_options['grid']['markings'] = markings
    flot_data.append({'data': state_data, 'lines': {'show': False}})

    result = [graph_options, flot_data, base]

    return HttpResponse(json.dumps(result))

def graphable(host, serviceList):
    global rra_path
    graphflags = []
    for service in serviceList:
        coilfile = rra_path + host + '/'	\
            + service['service_description'] + '.coil'
        rrd = rra_path + host + '/'   		\
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
                graphflags.append(1)
            except ValueError:
                for key in query.keys():
                    val = query.get(key)
                    if type() == type(query) and val.has_key('trend'):
                        graphflags.append(1)
                        break
                graphflags.append(0)

        else:
            graphflags.append(0)
    return graphflags    

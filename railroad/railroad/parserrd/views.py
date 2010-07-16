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

import rrdtool, simplejson, os, coil, types
from django.http import HttpResponse

def index(request, host, data, start, end, resolution='150'):
    global data_path
    rrd = data_path + 'rra/' + host + '/' + data + '.rrd'
    coilfile = data_path + 'rra/' + host + '/' + data + '.coil'
    railroadConf = 'railroadConf'
    statistics = 'statistics'
    trendSettings = ['color','stack','scale','display']


    # calculate custom resolution
    resolution = (int(end) - int(start)) / int(resolution)

    # rrdtool hates unicode strings, and Django gives us one, so convert to ascii
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

    graphOptions = {'xaxis': {'mode': 'time', 'min': 1000 * int(start), 'max': 1000 * int(end)}, 'yaxis': {}, 'legend': {'position': 'nw'}, 'selection': {'mode': 'x'}, 'pan': {'interactive': True}, 'grid': {}}

    graphTrend = coilstruct.get('trend',{})


    allLabels = rrdslice[1]

    labels = []

    for key in query.keys():
        val = query.get(key)
        if type(val) == type(query) and val.has_key('trend'):
            labels.append(key)

    length = len(labels)
        
    indices = range(length)
    dataset = {}


    # flotData and flotData are of the format
    # [ { label: "Foo", data: [ [10, 1], [17, -14], [30, 5] ] },
    #   { label: "Bar", data: [ [11, 13], [19, 11], [30, -7] ] } ]
    # See Flot Reference (http://flot.googlecode.com/svn/trunk/API.txt)
    flotData = [{'label': label, railroadConf: {}, 'data': []} for label in labels]
    stateData = []
    
    # Reading graph options
    for index in indices:
        key = labels[index]
        trend = query.get(key,{}).get('trend',{})
        if not(trend):
            continue

        settings = {}
        for var in trendSettings: 
            settings[var] = trend.get(var,'')

        if settings['display']:
            flotData[index]['lines'] = {'fill': 0.5 if settings['display'] == 'area' else 0}

        if settings['scale']:
            flotData[index][railroadConf]['scale'] = settings['scale']
        else:
            flotData[index][railroadConf]['scale'] = 1

        if settings['color']:
            flotData[index]['color'] = settings['color']

        if settings['stack']:
            flotData[index]['stack'] = True
            if index > 0:
                flotData[index-1]['stack'] = True

    # See above
    x = start * 1000

    transform = [allLabels.index(z) for z in labels]
    stateIndex = allLabels.index('_state')

    datapoints = zip(allLabels,rrdslice[2][0])
    for index in indices:
        label,data = datapoints[transform[index]]

        flotData[index][statistics] = {}
        flotData[index][statistics]['num'] = 0
        flotData[index][statistics]['sum'] = 0
        flotData[index][statistics]['max'] = 0
        flotData[index][statistics]['min'] = 99999999999999999999999
        if data:
            flotData[index][statistics]['max'] =                     \
                flotData[index][statistics]['min'] =                 \
                    data * flotData[index][railroadConf]['scale']


    for tuple in rrdslice[2]:
        datapoints = zip(allLabels,tuple)
    
        label,data = datapoints[stateIndex]
        stateData.append([x,data])

        for index in indices:
            label,data = datapoints[transform[index]]

            flotData[index][statistics]['num'] += 1
            if data:
                data *= flotData[index][railroadConf]['scale']
                flotData[index][statistics]['sum'] += data
                if data > flotData[index][statistics]['max']:
                    flotData[index][statistics]['max'] = data
                if data < flotData[index][statistics]['min']:
                    flotData[index][statistics]['min'] = data

            flotData[index]['data'].append([x,data])
    
        x += res

        #[[x,y * value] for x,y in d['data']]

    base = 1000
    max = 100

    if length > 0:
        value = query.get(labels[0],{}).get('trend',{}).get('base','')
        if value:
            base = int(value)

        max = flotData[0][statistics]['max']
        for index in indices:
            flotData[index][statistics]['avg'] = flotData[index][statistics]['sum'] / flotData[index][statistics]['num']
            if flotData[index][statistics]['max'] > max:
                max = flotData[index][statistics]['max']
            if flotData[index][statistics]['max'] > 0:
                flotData[index]['label'] = flotData[index]['label'] + ' (min: ' + str(flotData[index][statistics]['min']) + ', max: ' + str(flotData[index][statistics]['max']) + ', avg: ' + str(flotData[index][statistics]['avg']) + ')'


    graphOptions['yaxis']['max'] = max * 1.1

    if graphTrend:
        axis_max = graphTrend.get('axis_max','')
        if axis_max:
            graphOptions['yaxis']['max'] = axis_max * 1.1
    
    fill = graphOptions['yaxis']['max']

    if graphTrend:
        axis_label = graphTrend.get('axis_label','')
        if axis_label:
            graphOptions['yaxis']['label'] = axis_label
        
    for index in indices:
        del(flotData[index][railroadConf])

    #flotData = []
    colors = ['#33FF00','#FFFF00','#FF0000','#BEBEBE']
    markings = []
    state = stateData[0][1]
    if type(state) == types.FloatType:
        state = int(state) if float.is_integer(state) else 3
        markings.append({'xaxis': {'from': stateData[0][0]}, 'color': colors[state]})
    for x,y in stateData:
        if type(y) == types.FloatType:
            y = int(y) if float.is_integer(y) else 3
        if y != state:
            if type(state) == types.IntType:
                markings[-1]['xaxis']['to'] = x
            state = y
            if type(state) == types.IntType:
                markings.append({'xaxis': {'from': x}, 'color': colors[state]})
    if type(state) == types.FloatType:
        markings[-1]['xaxis']['to'] = stateData[-1][0]

    graphOptions['grid']['markings'] = markings
    flotData.append({'data': stateData, 'lines': {'show': False}})

    json = [graphOptions, flotData, base]

    return HttpResponse(simplejson.dumps(json))

def graphable(host, serviceList):
    global data_path
    graphflags = []
    for service in serviceList:
        coilfile = data_path + 'rra/' + host + '/' + service['service_description'] + '.coil'
        rrd = data_path + 'rra/' + host + '/' + service['service_description'] + '.rrd'
        if(os.path.exists(coilfile) and os.path.exists(rrd)):
            coilstring = open(coilfile).read()
            coilstruct = coil.parse(coilstring)
            query = coilstruct.get('query')

            # rrdtool hates unicode strings, and Django gives us one, so convert to ascii
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

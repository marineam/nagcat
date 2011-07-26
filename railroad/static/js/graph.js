/*
 * Copyright 2010 ITA Software, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/* This file primarily contains function definitions used in
 * plotting graphs for configurator.
 */

/******* GLOBALS ********/
// Base for data manipulation
// TODO: Find a way to remove global variable?
base = 0;

/******* Misc helper functions *******/
// Give strings a format function.
// Use it like this
//    "Hello {0}, how are you this fine {1}?".format(user_name, time_of_day);
//    Returns "Hello Mike, how are you this fine morning?"
String.prototype.format = function() {
    var formatted = this;
    for (var i = 0; i < arguments.length; i++) {
        var regexp = new RegExp('\\{'+i+'\\}', 'gi');
        formatted = formatted.replace(regexp, arguments[i]);
    }
    return formatted;
}

// An efficient function to unique values from a list
Array.prototype.uniqueList = function() {
    var oldList = this;
    var uniqDict = {}
    var uniqList = []

    for (var i=0; i<oldList.length; i++) {
        uniqDict[oldList[i]] = true;
    }
    for (var k in uniqDict) {
        uniqList.push(k);
    }
    return uniqList;
}

/******* FLOT HELPER FUNCTIONS *******/
$.plot.formatDate = function(d, fmt, monthNames) {
    var leftPad = function(n) {
        n = "" + n;
        return n.length == 1 ? "0" + n : n;
    };

    var r = [];
    var escape = false, padNext = false;
    var hours = d.getUTCHours();
    var form_data = localStorageGet('preference_panel');
    if  (form_data && form_data['localtime']) {
        hours = d.getHours();
    }
    var isAM = hours < 12;
    if (monthNames == null)
        monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    if (fmt.search(/%p|%P/) != -1) {
        if (hours > 12) {
            hours = hours - 12;
        } else if (hours == 0) {
            hours = 12;
        }
    }
    for (var i = 0; i < fmt.length; ++i) {
        var c = fmt.charAt(i);
            if (escape) {
                var form_data = localStorageGet('preference_panel');
                if  (form_data && form_data['localtime']) {
                    switch (c) {
                        case 'h': c = "" + hours; break;
                        case 'H': c = leftPad(hours); break;
                        case 'M': c = leftPad(d.getMinutes()); break;
                        case 'S': c = leftPad(d.getSeconds()); break;
                        case 'd': c = "" + d.getDate(); break;
                        case 'm': c = "" + (d.getMonth() + 1); break;
                        case 'y': c = "" + d.getFullYear(); break;
                        case 'b': c = "" + monthNames[d.getMonth()]; break;
                        case 'p': c = (isAM) ? ("" + "am") : ("" + "pm"); break;
                        case 'P': c = (isAM) ? ("" + "AM") : ("" + "PM"); break;
                        case '0': c = ""; padNext = true; break;
                    }
                }

                else {
                    switch (c) {
                        case 'h': c = "" + hours; break;
                        case 'H': c = leftPad(hours); break;
                        case 'M': c = leftPad(d.getUTCMinutes()); break;
                        case 'S': c = leftPad(d.getUTCSeconds()); break;
                        case 'd': c = "" + d.getUTCDate(); break;
                        case 'm': c = "" + (d.getUTCMonth() + 1); break;
                        case 'y': c = "" + d.getUTCFullYear(); break;
                        case 'b': c = "" + monthNames[d.getUTCMonth()]; break;
                        case 'p': c = (isAM) ? ("" + "am") : ("" + "pm"); break;
                        case 'P': c = (isAM) ? ("" + "AM") : ("" + "PM"); break;
                        case '0': c = ""; padNext = true; break;
                    }
                }
                if (c && padNext) {
                    c = leftPad(c);
                    padNext = false;
                }
                r.push(c);
                if (!padNext) {
                    escape = false;
                }
        }
        else {
            if (c == "%")
                escape = true;
            else
                r.push(c);
        }
    }
    return r.join("");
};

// Choose a base for graph axis
function chooseBase(max) {
    // Memoizes results!
    if (this.chooseBase.result != undefined &&
        this.chooseBase.result.max == max) {
        return result;
    }
    bases = ['', 'K', 'M', 'G', 'T'];
    for(interval = 0; interval < bases.length; interval++) {
        if(max / (Math.pow(base, interval)) <= base) {
            break;
        }
    }
    var result = [];
    result.interval = interval;
    result.bases = bases;
    result.max = max;
    return result;
}

// Generate ticks, passed as an option to Flot
function tickGenerator(range) {
    result = chooseBase(range.max);
    interval = result.interval

    final_base = Math.pow(base, interval);

    var noTicks = 0.3 * Math.sqrt($(".graph").height());

    var delta = ((range.max - range.min) / final_base) / noTicks,
        size, generator, unit, formatter, i, magn, norm;

    // Pretty rounding of base-10 numbers
    var dec = -Math.floor(Math.log(delta) / Math.LN10);

    magn = Math.pow(10, -dec);
    norm = delta / magn; // norm is between 1.0 and 10.0

    if (norm < 1.5)
        size = 1;
    else if (norm < 3) {
        size = 2;
        // special case for 2.5, requires an extra decimal
        if (norm > 2.25) {
            size = 2.5;
            ++dec;
        }
    }
    else if (norm < 7.5)
        size = 5;
    else
        size = 10;

    size *= magn;
    size *= final_base;

    var ticks = [];
    x = 0;
    for(tick = range.min; tick < range.max+size; tick+=size) {
        ticks[x++] = tick;
    }
    return ticks;
}

// Format ticks for displayed, passed as option to Flot
function tickFormatter(val, axis) {
    result = chooseBase(axis.max);
    interval = result.interval;
    bases = result.bases;

    final_base = (Math.pow(base, interval));

    // flot computes tickDecimals before dividing by final_base, so we update
    // tickDecimals accordingly
    if (final_base != 1) {
        tickDecimals = axis.tickDecimals;
        while (tickDecimals <= 3 &&
			(val / final_base).toFixed(tickDecimals) != val / final_base)
            tickDecimals++;

		if (tickDecimals <= 3)
			axis.tickDecimals = tickDecimals;
    }

    return (val / final_base).toFixed(axis.tickDecimals) + bases[interval];
}

function numberFormatter(n, base, labels) {
    if (base == undefined) {
        base = 1024;
    }
    if (labels == undefined) {
        labels = ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y', 'H'];
    }
    if (n==null) {
        return '';
    }
    label_index = 0;
    while (n > base && label_index < labels.length-1) {
        n /= base;
        label_index++;
    }

    return '{0}{1}'.format(n.toPrecision(3), labels[label_index]);
}

// Format a label, passed to Flot
function labelFormatter(label, series) {

    var checked = "";
    if (series.lines.show) {
        checked = " checked";
    }

    var stats = "";
    try {
        stats = ' (Cur: {0}, Max: {1}, Min: {2}, Avg: {3})'.format(
            numberFormatter(series.statistics.cur),
            numberFormatter(series.statistics.max),
            numberFormatter(series.statistics.min),
            numberFormatter(series.statistics.avg)
        );
    } catch(e) {
        // graph doesn't have cur,max,min,avg, so skip them.
    }

    var out = ('<input type="checkbox" id="{0}" class="removeSeries"{1}>' +
               '{0}{2}</input>').format(label, checked, stats);

    return out;
}

/******* GRAPH GENERATION/MANIPULATION *******/

// Takes the raw data and sets up required Flot formatting options
function formatGraph(element, data) {
    base = data.base;

    var first = true;
    var max = null;
    for (var i=0; i < data.data.length; i++) {
        if (data.data[i].lines.show) {
            for (var j=0; j < data.data[i].data.length; j++) {
                var val = data.data[i].data[j][1];
                if (( val > max && val != null) || first ) {
                    max = val;
                    first = false;
                }
            }
        }
    }

    data.options.yaxis.max = max * 1.2;
    if ( max ) {
        data.options.yaxis.show = true;
        data.options.yaxis.ticks = tickGenerator;
        data.options.yaxis.tickFormatter = tickFormatter;
    }
    else {
        data.options.yaxis.ticks = [];
    }
    // TODO: Cleanup legend and axis label creation
    data.options.legend = {}
    data.options.legend.container = $(element).next('.legend');
    data.options.legend.labelFormatter = labelFormatter;
    return data;
}

function getGraphDataByData(element) {
    var slug = $(element).attr('name');
    var hostname = $(element).data('host');
    var servicename = $(element).data('service');
    var start = $(element).data('start');
    var end = $(element).data('end');
    var uniq = $(element).attr('id');
    var data = {
        "host" : hostname,
        "service" : servicename,
        "uniq" : uniq,
        "start" : start,
        "end" : end,
    };
    if ($(element).data('data')) {
        for (var i=0; i < $(element).data('data').data.length; i++) {
            if ($(element).data('data').data[i].label) {
                if (!data['labels']) {
                    data['labels'] = {};
                }
                var label = $(element).data('data').data[i].label;
                var show = $(element).data('data').data[i].lines.show;
                data['labels'].label = show;
            }
        }
    }
    return data
}

function fetchAndDrawGraphDataByDiv () {
    var graph_divs = $('.graph_container');
    var ajaxData = [];
    graph_divs.each(function () {
        var element = $(this).children('.graph');
        var slug = $(element).attr('name');
        graphs = $(slug).each(function (index, element) {
            $(element).attr('id', index);
        });
        var hostname = $(element).children('.graph_hostname').attr('id');
        var serviceName = $(element).children('.graph_service_name').attr('id');
        var start = $(element).children('.graph_start').attr('id');
        var end = $(element).children('.graph_end').attr('id');
        var uniq = $(element).attr('id');

        var data = {
            "host" : hostname,
            "service" : serviceName,
            "start" : start,
            "end" : end,
            "uniq" : uniq,
        };
        ajaxData.push(data);
    });
    ajaxData = JSON.stringify(ajaxData);
    $.ajax({
        url: '/railroad/graphs',
        data: 'graphs=' + ajaxData,
        type: 'POST',
        async: true,
        dataType: 'json',
        success: function (data, textStatus, XMLHttpRequest) {
            for (var i=0; i < data.length; i++) {
                var elem;
                if (data[i].uniq) {
                    elem = $('.{0}#{1}'.format(data[i].slug, data[i].uniq));
                } else {
                    elem = $('.{0}'.format(data[i].slug));
                }
                if (data[i].data) {
                    drawGraph(elem, data[i]);
                } else {
                    $(elem).data('host', data[i].host);
                    $(elem).data('service', data[i].service);
                }
            }
        },
        error: function () {
            console.log('There was an error in obtaining the data for graphs');
        }
    });
}

function getGraphDataByDiv(element) {
    var slug = $(element).attr('name');
    graphs = $('.{0}'.format(slug)).each(function (index, element) {
        $(element).attr('id', index);
    });
    var hostname = $($(element).children('.graph_hostname')).attr('id');
    var servicename = $($(element).children('.graph_service_name')).attr('id');
    var start = $($(element).children('.graph_start')).attr('id');
    var end = $($(element).children('.graph_end')).attr('id');
    var uniq = $(element).attr('id');
    var data = {
        "host" : hostname,
        "service": servicename,
        "uniq" : uniq,
        "start": start,
        "end" : end,
    };
    return data;
}
function addHTML(ajaxData) {
    var graphWarningThreshold = 100;
    if (localStorageGet('preference_panel')) {
        if (localStorageGet('preference_panel')['graphWarningTreshold']) {
            graphWarningTreshold =
                localStorageGet('preference_panel')['graphWarningThreshold'];
        }
    }
    $.ajax({
        data: ajaxData,
        url: '/railroad/configurator/graph',
        type: 'POST',
        async: true,
        dataType: 'html',
        success: function (html, textStatus, XMLHttpRequest) {
            html = html.trim();
            if (!html) {
                console.log('No html returned!');
                return;
            }

            var numServices = $(html).closest('.service_row').length;
            if ( numServices > graphWarningThreshold) {
                var confText = 'You asked to add {0} graphs'.format(numServices)
                    + '. Would you like to continue?';
                var conf = confirm(confText);
                if (!conf) {
                    return;
                }
            }

            $(html).appendTo('#graphs');
            update_number_graphs();


            var services = $('.service_row');
            services.each(function (index, elemRow) {
                collapse_or_expand(elemRow);
            });

            fetchAndDrawGraphDataByDiv();

        },
        error: function () {
            console.log('failed to add graph html');
        }
    });
}


// Plots the data in the given element
function drawGraph (elemGraph, data) {
    redrawGraph(elemGraph, data)
    if(data.options.yaxis.label) {
    // if there isn't already a ylabel
        if (elemGraph.siblings('.ylabel').length == 0) {
            $(elemGraph).before('<div class="ylabel">' +
                data.options.yaxis.label + '</div>');
        }
        if ( $(elemGraph).css('display') === 'none' ) {
            $(elemGraph).siblings('.ylabel').css('display', 'none');
        }
    }
    $(elemGraph).bind('plotselected', function (event, ranges) {
        if ($('#sync').prop('checked')) {
            graphs = $('.graph');
        } else {
            graphs = $(elemGraph);
        }
        graphs_to_update = [];
        graphs.each(function(index, element) {
            $(element).removeClass('ajax');
            $(element).data('start', parseInt(ranges.xaxis.from / 1000));
            $(element).data('end', parseInt(ranges.xaxis.to / 1000));
            if ( $(element).data('data')) {
                graphs_to_update.push(getGraphDataByData(element));
            }
        });
        // If there are graphs we need new data for, fetch new data!
        if ( graphs_to_update.length > 0 ) {
            ajaxcall = JSON.stringify(graphs_to_update);
            $.ajax ({
                url: '/railroad/graphs',
                data: {'graphs': ajaxcall},
                type: 'POST',
                async: true,
                dataType: 'json',
                success: function (data, textStatus, XMLHttpRequest) {
                    for (var i=0; i < data.length; i++) {
                        if (data[i].data) {
                            elemGraph = $('.{0}'.format(data[i]['slug']));
                            redrawGraph(elemGraph, data[i]);
                            if(data[i].options.yaxis.label) {
                            }
                        }
                    }
                },
               error: function (XMLHttpRequest, textStatus, errorThrown) {
                    alert ("Something went wrong in getting new data");
                }
            });
        }
    });

    var prevItem = null;
    $(elemGraph).parent().bind('plothover', function(event, pos, item) {
        if (item) {
            if(item != prevItem) {
                prevItem = item;
                var label = '<h3>{0} - {2}</h3><p>({1})</p>'.format(
                    item.series.label, new Date(pos.x).toString(),
                    numberFormatter(pos.y))

                showTooltip(item.pageX, item.pageY, label);
            }
        } else {
            $('#tooltip').remove();
        }
    });

    $('.removeSeries').live('click', function () {
        var elemGraph = $(this).closest('.legend').siblings('.graph');
        if (elemGraph.data('data')) {
            data = elemGraph.data('data');
            for (var i=0; i < data.data.length; i++) {
                if (data.data[i].label == $(this).attr('id')) {
                    data.data[i]['lines']['show'] ^= true; // toggle
                }
            }
            redrawGraph(elemGraph, data);
        }
    });
    // elemGraphDates keeps the line below it < 80 chars
    var elemGraphDates = $(elemGraph).siblings('.daterange').children('input');
    var datePickers = $(elemGraphDates).datetimepicker({
        onClose: function(selectedDate) {
            updateZoom(datePickers[0], datePickers[1]);
        },
        changeMonth: true,
        changeYear: true,
    });
    $(datePickers[0]).datetimepicker('setDate',
            new Date(elemGraph.data('start') * 1000));
    $(datePickers[1]).datetimepicker('setDate',
            new Date(elemGraph.data('end') * 1000));

    $(elemGraph).siblings('.graphloading').remove();
}

function redrawGraph(element, data) {
    data = formatGraph(element, data);
    $(element).data('plot', $.plot($(element), data.data, data.options));
    $(element).siblings('.graphloading').text('Rendering Graph...');

    $(element).data('data', data);
    $(element).data('start', data.start);
    $(element).data('end', data.end);
    $(element).data('host', data.host);
    $(element).data('service', data.service);
}

function showTooltip(x, y, label) {
    $('#tooltip').remove()
    $('<div id="tooltip">{0}</div>'.format(label)).appendTo('body')
        .css({'left': x, 'top': y});
}

function updateZoom(from, to) {
    var start = $(from).datetimepicker('getDate').getTime();
    var end = $(to).datetimepicker('getDate').getTime();

    var graph = $(from).parent().siblings('.graph').first();
    $(graph).trigger('plotselected', {'xaxis': {'from': start, 'to': end}});
}

// Automatically fetch new data for graphs that have the class 'ajax'
function autoFetchData() {
    graphs = [];
    $('.graph.ajax').each(function (index, element) {
        graph = getGraphDataByData(element);
        graphs.push(graph);
    });
    ajaxcall = JSON.stringify(graphs);
    $.ajax({
        dataType: 'json',
        url: '/railroad/graphs',
        data: {'graphs': ajaxcall},
        type: 'POST',
        async: true,
        success: function (data, textStatus, XMLHttpRequest) {
            console.log('autoFetchData success');
            for (var i=0; i < data.length; i++){
                var element = $('.{0}'.format(data[i]['slug']));
                if (data[i].data) {
                    redrawGraph(element, data[i]);
                }
            }
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            console.log ("Auto Fetch data failed." + XMLHttpRequest + ' ' +
                textStatus + ' ' + errorThrown);
        }
    });
    setTimeout(autoFetchData, 600 * 1000);
}

// Sort the graphs.
function reverse(func) {
    return function(a,b) {
        return func(b,a);
    }
}
function makeComparer(val) {
    return function(a,b) {
        var va = val(a);
        var vb = val(b);
        if (va > vb) {
            return 1;
        } else if (va < vb) {
            return -1;
        } else {
            return 0;
        }
    }
}
var sorts = {
    'service': makeComparer(function(e) {
            var s = $(e).find('td.status_text dd[name=service]').last().text();
            s = s.toLowerCase().trim();
            return s;
        }),
    'host': makeComparer(function(e) {
            var h = $(e).find('td.status_text dd[name=host]').first().text();
            h = h.toLowerCase().trim();
            return h;
        }),
    'status': reverse(makeComparer(function(e) {
            e_td = $(e).find('td.status_text');
            if (e_td.hasClass('state_ok')) {
                return 0;
            } else if (e_td.hasClass('state_warning')) {
                return 1;
            } else if (e_td.hasClass('state_critical')) {
                return 2;
            } else {
                return 3;
            }
        })),
    'value': makeComparer(function(e) {
            var plot = $(e).find('.graph').first().data('plot');
            if (!plot) {
                return NaN;
            }
            series = plot.getData()[0].data;
            latest = parseInt(series[series.length-1][1]);
            return latest;
        }),
    'duration': makeComparer(function(e) {
            var text = $(e).find('td.status_text dd[name=duration]').text();
            var dur = parseInt(text);
            if (text.indexOf('minute') != -1) {
                dur *= 60;
            } else if (text.indexOf('hour') != -1) {
                dur *= 60 * 60;
            } else if (text.indexOf('day') != -1) {
                dur *= 60 * 60 * 24;
            }
            console.log(text + ' = ' + dur);
            return dur;
        })
}

function sortGraphs(name, reversed) {
    var sorter = sorts[name];
    if (reversed) {
        sorter = reverse(sorter);
    }
    var rows = $('tr.service_row');
    rows = rows.sort(sorter);
    $(rows).appendTo('#graphs');
}

/******* Local Storage Hooks *******/
function updateDebug() {
    if (localStorageGet('debug')) {
        $('#debug input').prop('checked', true);
        $('#debug ul li').remove();
        for (var prop in localStorage) {
            var desc = localStorage[prop];
            $('#debug ul').append('<li>({0}) {1}: {2}</li>'.format(typeof(desc),
                                                                   prop, desc));
        }
        $('#debug ul').append('<li><a href="#">Reset localStorage</a></li>');
    } else {
        $('#debug input').prop('checked', false);
        $('#debug ul li').remove();
    }
}

function localStorageSupport() {
    try {
        return 'localStorage' in window && window['localStorage'] !== null;
    } catch (e) {
        return false;
    }
}

function localStorageDelete(key) {
    if (localStorageSupport()) {
        if (localStorageGet(key)) {
            delete localStorage[key];
        }
    }
}

function localStorageSet(key, value) {
    if (localStorageSupport()) {
        var json = JSON.stringify(value)
        localStorage[key] = json;
        updateDebug();
        return true;
    }
    // Should we try other methods of storing data?
    return false;
}

function localStorageGet(key) {
    if (localStorageSupport()) {
        var ob;
        try {
            ob = JSON.parse(localStorage[key]);
        } catch(e) {
            ob = localStorage[key];
        }
        return ob;
    }
    // Should we try other methods of storing data?
    return null;
}

function localStorageClear() {
    if (localStorageSupport()) {
        localStorage.clear();
        updateDebug();
        return true;
    }
    return false;
}
/**** Expand/Collapse the graph rows ****/
function auto_expansion() {
    states = {}
    $('#expansion_by_type input').each(function(index, elem) {
        states[elem.id] = $(elem).prop('checked');
    });
    $('.service_row').each(function(index, elem) {
        for (var s in states) {
            if ($(elem).children('td.status_text').hasClass(s)) {
                if (states[s]) {
                    expand_row(elem);
                } else {
                    collapse_row(elem);
                }
            }
        }
    });
}
function collapse_or_expand(row) {
    states = {};
    $('#expansion_by_type input').each(function(index, element) {
        states[element.id] = $(element).prop('checked');
    });
    for (var s in states) {
        if ($(row).children('td.status_text').hasClass(s)) {
            if (states[s]) {
                expand_row(row);
            } else {
                collapse_row(row);
            }
        }
    }
}
function collapse_row(row) {
    // Hide the graph and status text
    var container = $(row).children('.graph_container').first();
    container.children().not('p').hide();
    if ($(container).children('.nograph').length < 1) {
        container.append('<p class="graphcollapsed">Graph Collapsed</p>');
    }
    $(row).find('.status_text dt').hide();
    $(row).find('.status_text dd').css({'width':'auto', 'margin-right':'10px'})
        .not('[name=host]').not('[name=service]').hide();
}
function expand_row(row) {
    // Hide the graph and status text
    $(row).children('.graph_container').children('.graphcollapsed').remove();
    $(row).children('.graph_container').children().show();
    $(row).find('.status_text dt').show();
    $(row).find('.status_text dd').css({'width': '265px', 'margin-right': 0})
        .show();
}

function update_number_graphs() {
    $('#stats #service_count').html('{0} Services'.format(
        $('.service_row').length));
    $('#stats .state_ok').html('{0}'.format(
        $('.service_row .state_ok').length));
    $('#stats .state_warning').html('{0}'.format(
        $('.service_row .state_warning').length));
    $('#stats .state_critical').html('{0}'.format(
        $('.service_row .state_critical').length));
    $('#stats .state_unknown').html('{0}'.format(
        $('.service_row .state_unknown').length));
}

var update_hidden_count = function() {
    if ($('#hiddenCount').length == 0) {
        $('#stats').append('<span id="hiddenCount"></span>');
    }
    var count = $('.service_row').filter(':hidden').length;
    if (count > 0) {
        $('#hiddenCount').html('{0} hidden'.format(count));
    } else {
        $('#hiddenCount').remove();
    }
    $('#stats .state_count').each(function(index, element) {
        var buttonClass = $(this).attr('name');
        var checkp = $('.service_row').children('.status_text')
            .filter('.' + buttonClass + ':hidden').length > 0;
        $(this).data('checkp', checkp);
        $(element).css({'opacity': checkp ? 0.4 : 1.0});
    });
}

function generateState() {
    servicesList = [];
    services = $('.service_row');
    services.each(function(index, element) {
        var elemGraph = $(element).find('.graphInfo');
        var service = getGraphDataByData($(elemGraph));
        servicesList.push(service);
    });
    return servicesList;
}

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

/******* GLOBALS ********/

// Base for data manipulation
// TODO: Find a way to remove global variable?
base = 0;

/******* FLOT HELPER FUNCTIONS *******/
$.plot.formatDate = function(d, fmt, monthNames) {
    var leftPad = function(n) {
        n = "" + n;
        return n.length == 1 ? "0" + n : n;
    };

    var r = [];
    var escape = false, padNext = false;
    var hours = d.getUTCHours();
    var form_data = localStorageGet('form_configurator');
    if  (form_data && form_data['localtime']) {
        hours = d.getHours();
    }
    var isAM = hours < 12;
    if (monthNames == null)
        monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

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
                var form_data = localStorageGet('form_configurator');
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
    var result = new Array();
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

// Format a label, passed to Flot
function labelFormatter(label, series) {
    //return '<input type="button" id="'+label+'" value="'+label+'" class="removeSeries"></input>';

    var checked = "";
    if (series.lines.show) {
        var checked = " checked";
    }
    var label = '<input type="checkbox" id="{0}" class="removeSeries"{1}>{0}</input>'.format(label, checked);
    label += ' (Cur: {0}, Max: {1}, Min: {2}, Avg: {3})'.format(
        series.statistics.cur.toPrecision(4), series.statistics.max.toPrecision(4),
        series.statistics.min.toPrecision(4), series.statistics.avg.toPrecision(4));

    return label;
}

/******* GRAPH GENERATION/MANIPULTION *******/

// Takes the raw data and sets up required Flot formatting options
function formatGraph(element, data) {
    base = data.base;

    data.options.yaxis.ticks = tickGenerator;
    data.options.yaxis.tickFormatter = tickFormatter;

    // TODO: Cleanup legend and axis label creation
    data.options.legend = {}
    data.options.legend.container = $(element).next('.legend');
    data.options.legend.labelFormatter = labelFormatter;
    return data;
}

function createGraphs(data) {
    var params = [];
    for (var i=0; i<data.length; i++) {
        params.push({
            'host': data[i]['host'],
            'service': data[i]['service'],
        });
    }
    params = {"graphs": JSON.stringify(params)}

    $.ajax({
        data: params,
        url: '/railroad/configurator/graph',
        dataType: 'html',
        success: function (html, textStatus, XMLHttpRequest) {
            $(html).appendTo('#graphs');

            for (var i=0; i < data.length; i++) {
                var element = $('#{0}'.format(data[i]['slug']));
                element.data('host', data[i]['host']);
                element.data('service', data[i]['service']);
                if (data[i].data) {
                    drawGraph(element, data[i]);
                }
            }
        },
        error: function() {
            console.log('fail');
        }
    });
    // get the graphs collapsed/expanded as they should be.
    auto_expansion();
}

// Plots the data in the given element
function drawGraph (elemGraph, data) {
                data = formatGraph(elemGraph, data);
                elemGraph.data('plot', $.plot(elemGraph, data.data, data.options));
                elemGraph.data('start', data['start']);
                elemGraph.data('end', data['end']);
                elemGraph.data('host', data['host']);
                elemGraph.data('service', data['service']);
                elemGraph.data('data', data)
                if(data.options.yaxis.label) {
                // if there isn't already a ylabel
                    if (elemGraph.siblings('.ylabel').length == 0) {
                        $(elemGraph).before('<div class="ylabel">' +
                            data.options.yaxis.label + '</div>');
                    }
                }
        $(elemGraph).bind('plotselected', function (event, ranges) {
                elemGraph.removeClass('ajax');
                if ($('#sync').prop('checked')) {
                    graphs = $('.graph');
                } else {
                    graphs = $(element);
                }
                graphs_to_update = [];
                graphs.each(function(index, element) {
                    graph = {};
                    // Count the number of data points, if they aren't enough, we need to fetch more data
                    var count=0;
                    for (var j=0; j < data.data[0].data.length; j++) {
                        if ( data.data[0].data[j][0] > ranges.xaxis.from && data.data[0].data[j][0] < ranges.xaxis.to ) {
                            count++;
                        }
                    }
                    // If there aren't enought data points, get MOAR DATA!
                    if ( count < 50 ) {
                        graph = {
                            "host" : $(element).data('host'),
                            "service" : $(element).data('service'),
                            "start" : parseInt(ranges.xaxis.from / 1000),
                            "end" : parseInt(ranges.xaxis.to / 1000),
                        };
                        graphs_to_update.push(graph);
                    } else {
                    // else zoom in
                        // If there is data to graph, graph data! Otherwise, do nothing.
                        if ($(element).data('data')) {
                            data = $(element).data('data')
                            $(element).data('plot', $.plot(element, data.data, $.extend(true, {}, data.options, {
                                    xaxis: { min: ranges.xaxis.from, max: ranges.xaxis.to }
                                    })));
                            $(element).data('start', data.start);
                            $(element).data('end', data.end);
                        }
                    }
                });
        // If there are graphs we need new data for, fetch new data!
            if ( graphs_to_update.length > 0 ) {
                ajaxcall = JSON.stringify(graphs_to_update);
                $.ajax ({
                    url: '/railroad/graphs?graphs=' + ajaxcall,
                    dataType: 'json',
                    success: function (data, textStatus, XMLHttpRequest) {
                        for (var i=0; i < data.length; i++) {
                            if (data[i].data) {
                                element = $('#{0}'.format(data[i]['slug']));
                                data[i] = formatGraph(elemGraph, data[i]);
                                elemGraph.data('plot', $.plot(elemGraph, data[i].data, data[i].options));
                                elemGraph.data('start', data[i]['start']);
                                elemGraph.data('end', data[i]['end']);
                                elemGraph.data('host', data[i]['host']);
                                elemGraph.data('service', data[i]['service']);
                                elemGraph.data('data', data[i])
                                if(data[i].options.yaxis.label) {
                                // if there isn't already a ylabel
                                    if (elemGraph.siblings('.ylabel').length == 0) {
                                        elemGraph.before('<div class="ylabel">' +
                                            data[i].options.yaxis.label + '</div>');
                                    }
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
        $('.removeSeries').live('click', function () {
            var elemGraph = $(this).closest('.legend').siblings('.graph');
            if (elemGraph.data('data')) {
                data = elemGraph.data('data');
                for (var i=0; i < data.data.length; i++) {
                    if (data.data[i].label == $(this).attr('id')) {
                        if (!data.data[i]['lines']) {
                            data.data[i]['lines'] = {'show': true};
                        }
                        data.data[i]['lines']['show'] ^= true; // toggle
                    }
                }
            }
            elemGraph.data('plot', $.plot(elemGraph, data.data, data.options));
            elemGraph.data('data', data);
        });

}
// Creates a graph
function createGraph(element, path, callback, zoom) {
    // If the graph isn't busy
    if(!$(element).data('busy')) {
        $(element).data('busy', true);
        $(element).append('<div class="throbber"></div>');
        $(element).remove('.empty');
        var ajaxmanager = $.manageAjax.create('createGraph', {
            queue: true,
            cacheResponse: true,
            maxRequests: 4,
        });
        ajaxmanager.add({
            url: '/railroad/parserrd/' + path,
            dataType: 'json',
            success: function(data) {
                // If we are zooming and there's no data, just bail with an
                // error
                if(zoom && data.empty) {
                    plot = $(element).data('plot');
                    plot.clearSelection();
                    $(element).append('<div class="error">no data to ' +
                                      'zoom</div>');
                    // Nice fadeOut won't let us remove the element, so use a
                    // callback
                    $(element).find('.error')
                              .delay(500)
                              .fadeOut(500,
                                       function() {
                                           $(this).remove();
                                       });
                } else {
                    data = formatGraph(element, data);
                    $(element).data('plot',
                                    $.plot($(element),
                                    data.data,
                                    data.options));
                    $(element).data('start',
                                    data.start);
                    $(element).data('end',
                                    data.end);
                    if(data.options.yaxis.label) {
                        // if there isn't already a ylabel
                        if ($(element).siblings('.ylabel').length == 0) {
                            $(element).before('<div class="ylabel">' +
                                              data.options.yaxis.label + '</div>');
                        }
                    }
                    if(data.empty == true) {
                        $(element).append('<div class="empty">no data</div>');
                    }

                    update = $(element).closest('.graph_container') .find('.update')
                                 .html('updated: ' + data.current_time);

                    // get the graphs collapsed/expanded as they should be.
                    auto_expansion();

                    if(callback != null) {
                        callback(data);
                    }
                }
                $(element).find('.throbber').remove();
            },
            // If there's an error, toss out a warning about it
            error: function(request, status, error) {
                plot = $(element).data('plot');
                if(zoom) {
                    plot.clearSelection();
                }
                $(element).find('.throbber').remove();
                $(element).append('<div class="error">error</div>');
                if(zoom) {
                    // Nice fadeOut won't let us remove the element, so use a
                    // callback
                    $(element).find('.error')
                              .delay(500)
                              .fadeOut(500,
                                       function() {
                                           $(this).remove();
                                       });
                }
            }
        });
    // Release the graph
    $(element).data('busy', null);
    }
}

function parseAllGraphs(graphs) {
    var ajaxcalls = [];

    // Don't set up graphs already set up
    graphs.each(function (index, element) {
        var ajaxcall = {};
        //$(element).addClass('setup');
        // Store the graph data for usage later
        path = $(element).find('a').attr('href');
        splitPath = path.split('/');
        $(element).data('host', splitPath[0]);
        $(element).data('service', splitPath[1]);
        $(element).data('start', splitPath[2]);
        $(element).data('end', splitPath[3]);
        $(element).data('res', splitPath[4]);

        ajaxcall['host'] = splitPath[0];
        ajaxcall['service'] = splitPath[1];
        ajaxcall['start'] = splitPath[2];
        ajaxcall['end'] = splitPath[3];
        ajaxcall['res'] = splitPath[4];

        ajaxcalls.push(ajaxcall);
    });

    createGraphs(JSON.stringify(ajaxcalls));

    // Allow for zooming
    //$(element).bind('plotselected', function (event, ranges) {
    //    // The graph isn't busy anymore, allow updates
    //    $(element).data('busy', null); 

    //    // If we are supposed to sync the graphs, loop over all graphs
    //    if($('#sync').attr('checked')) {
    //        graphs = $('.graph');
    //        // Allow us to zoom even when it makes no sense if we are
    //        // synced
    //        zoom = false;
    //    // Otherwise only loop over the graph associated with this button
    //    } else {
    //        graphs = $(element);
    //        zoom = true;
    //    }

    //    graphs.each(function(index, element) {

    //        serviceData = $(element).data();

    //        path = [serviceData.host,
    //                serviceData.service,
    //                parseInt(ranges.xaxis.from / 1000),
    //                parseInt(ranges.xaxis.to / 1000),
    //                serviceData.res].join('/');

    //        createGraph(element,
    //                    path,
    //                    function() {
    //                        $(element).removeClass('ajax');
    //                        zoomButton = $(element)
    //                                        .closest('.graph_container')
    //                                        .find('.zoom');
    //                        selected = $(element)
    //                                        .closest('.graph_container')
    //                                        .find('.selected');
    //                        selected.removeClass('selected');
    //                        zoomButton.css('visibility', 'visible');
    //                        zoomButton.addClass('selected');
    //                    },
    //                    zoom);
    //    });
    //});
    //$(element).bind('plotselecting', function() {
    //    // If we are selecting, mark the graph as busy so no AJAX fires
    //    $(element).data('busy', true);
    //});

}
// Parse and setup graphs on the page
function parseGraphs(index, element) {

    // Don't set up graphs already set up
    $(element).addClass('setup');

    // Store the graph data for usage later
    path = $(element).find('a').attr('href');
    splitPath = path.split('/');
    $(element).data('host', splitPath[0]);
    $(element).data('service', splitPath[1]);
    $(element).data('start', splitPath[2]);
    $(element).data('end', splitPath[3]);
    $(element).data('res', splitPath[4]);

    createGraph(element, path, sortGraphs);

    // Allow for zooming
    $(element).bind('plotselected', function (event, ranges) {
        // The graph isn't busy anymore, allow updates
        $(element).data('busy', null); 

        // If we are supposed to sync the graphs, loop over all graphs
        if($('#sync').attr('checked')) {
            graphs = $('.graph');
            // Allow us to zoom even when it makes no sense if we are
            // synced
            zoom = false;
        // Otherwise only loop over the graph associated with this button
        } else {
            graphs = $(element);
            zoom = true;
        }

        graphs.each(function(index, element) {

            serviceData = $(element).data();

            path = [serviceData.host,
                    serviceData.service,
                    parseInt(ranges.xaxis.from / 1000),
                    parseInt(ranges.xaxis.to / 1000),
                    serviceData.res].join('/');

            createGraph(element,
                        path,
                        function() {
                            $(element).removeClass('ajax');
                            zoomButton = $(element)
                                            .closest('.graph_container')
                                            .find('.zoom');
                            selected = $(element)
                                            .closest('.graph_container')
                                            .find('.selected');
                            selected.removeClass('selected');
                            zoomButton.css('visibility', 'visible');
                            zoomButton.addClass('selected');
                        },
                        zoom);
        });
    });
    $(element).bind('plotselecting', function() {
        // If we are selecting, mark the graph as busy so no AJAX fires
        $(element).data('busy', true);
    });

}

function autoFetchDataNew() {
    graphs = [];
    $('.graph.ajax').each(function (index, element) {
        host = $(element).data('host');
        service = $(element).data('service');
        graph = {
            "host" : host,
            "service": service,
        };
        graphs.push(graph);
    });
    ajaxcall = JSON.stringify(graphs);
    $.ajax({
        dataType: 'json',
        url: '/railroad/graphs?graphs=' + ajaxcall,
        success: function (data, textStatus, XMLHttpRequest) {
            for (var i=0; i < data.length; i++){
                var element = $('#{0}'.format(data[i]['slug']));
                if (data[i].data) {
                    drawGraph(element, data[i]);
                }
            }
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            alert ("Auto Fetch data failed");
        }
    });
    setTimeout(autoFetchDataNew, 600 * 1000);
}





// Function to automatically update any graphs which are set to ajax load
function autoFetchData() {
    $('.graph.ajax').each(function(index, element) {
        serviceData = $(element).data();
        time = new Date();
        end = parseInt(time.getTime() / 1000);
        start = parseInt(end - 60 * 60 * 24);

        path = [serviceData.host,
                serviceData.service,
                start,
                end,
                serviceData.res].join('/');

        createGraph(element, path);
    });
    setTimeout(autoFetchData, 60 * 1000);
}

// Sort the graphs.
function reverse(func) {
    return function(a,b) {
        return func(b,a);
    }
}
function makeComparer(val) {
    return function(a,b) {
        return val(a) > val(b);
    }
}
var sorts = {
    'service': makeComparer(function(e) {
            return $(e).find('td.status_text h2').last().text();
        }),
    'host': makeComparer(function(e) {
            return $(e).find('td.status_text h2').first().text();
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
        })
}
function sortGraphs() {
    //console.log('sorting... #of trs: {0}'.format($('tr.service_row').length));
    var name = $('#sortby').val();
    var sorter = sorts[name];
    if ($('#reverse_sort').prop('checked')) {
        sorter = reverse(sorter);
    }
    $('tr.service_row').sort(sorter).appendTo('#graphs');
}

/******* Local Storage Hooks *******/
function updateDebug() {
    if (localStorageGet('debug')) {
        $('#debug input').prop('checked', true);
        $('#debug ul li').remove();
        for (var prop in localStorage) {
            var desc = localStorage[prop];
            $('#debug ul').append('<li>({0}) {1}: {2}</li>'.format(typeof(desc), prop, desc));
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

/******* Misc helper functions *******/
// Give strings a format function.
// Use it like this
//    "Hello {0}, how are you this find {1}?".format(user_name, time_of_day);
//    Returns "Hello Mike, how are you this fine morning?"
String.prototype.format = function() {
    var formatted = this;
    for (var i = 0; i < arguments.length; i++) {
        var regexp = new RegExp('\\{'+i+'\\}', 'gi');
        formatted = formatted.replace(regexp, arguments[i]);
    }
    return formatted;
};

/**** Expand/Collapse the graph rows ****/
function auto_expansion() {
    console.log('auto');
    states = {}
    $('#expansion_by_type input').each(function(index, elem) {
        states[elem.id] = $(elem).prop('checked');
    });
    console.log(states);
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
function collapse_row(row) {
    // Hide the graph and status text
    $(row).children('.graph_container').children().hide();
    $(row).children('.status_text').children('p').hide();
    $(row).children('.status_text').children('h2').css({'display': 'inline'});

    // change the button to expand
    $(row).children('.controls').children('div').removeClass('collapse_row');
    $(row).children('.controls').children('div').addClass('expand_row');
}
function expand_row(row) {
    // Hide the graph and status text
    $(row).children('.graph_container').children().show();
    $(row).children('.status_text').children('p').show();
    $(row).children('.status_text').children('h2').css({'display': 'block'});

    // change the button to expand
    $(row).children('.controls').children('div').removeClass('expand_row');
    $(row).children('.controls').children('div').addClass('collapse_row');
}


/******* DOM HOOK SETUP *******/

// Execute setup code when page loads
$(document).ready(function() {

    /**** GRAPH SETUP ****/

    // Bind the graph time range selection buttons
    $('.options ul li').live('click', function() {
        clicked = $(this);
        // If we are supposed to sync the graphs, loop over all graphs
        if($('#sync').attr('checked')) {
            graphs = $('.graph');
        // Otherwise only loop over the graph associated with this button
        } else {
            graphs = $(this).closest('.graph_container')
                             .find('.graph');
        }
        graphs.each(function(index, graph) {
            button = $(graph).closest('.graph_container')
                             .find('.year');
            time = new Date();
            end = parseInt(time.getTime() / 1000);

            // Depending on which button is hit, change the behavior
            // TODO: Look at possibilities at cleaning this up

            if(clicked.hasClass('zoom')) {
                return;
            }

            $(graph).closest('.graph_container')
                    .find('.zoom')
                    .css('visibility', 'hidden');

            if(clicked.hasClass('reset')) {
                $(graph).addClass('ajax');
            } else {
                $(graph).removeClass('ajax');
            }
            if(clicked.hasClass('day') || clicked.hasClass('reset')) {
                start = parseInt(end - 60 * 60 * 24);
            } else if(clicked.hasClass('week')) {
                start = parseInt(end - 60 * 60 * 24 * 7);
            } else if(clicked.hasClass('month')) {
                start = parseInt(end - 60 * 60 * 24 * 30);
            } else if(clicked.hasClass('year')) {
                start = parseInt(end - 60 * 60 * 24 * 365);
            }

            serviceData = $(graph).data();

            path = [serviceData.host,
                    serviceData.service,
                    start,
                    end,
                    serviceData.res].join('/');

            createGraph(graph,
                        path,
                        function() {
                            $(graph).closest('.graph_container')
                                    .find('.options .selected')
                                    .removeClass('selected');
                            // This is pretty horrible, perhaps there is a
                            // better way
                            if(clicked.hasClass('reset')) {
                                buttonClass = '.reset';
                            } else if(clicked.hasClass('day')) {
                                buttonClass = '.day';
                            } else if(clicked.hasClass('week')) {
                                buttonClass = '.week';
                            } else if(clicked.hasClass('month')) {
                                buttonClass = '.month';
                            } else if(clicked.hasClass('year')) {
                                buttonClass = '.year';
                            } else if(clicked.hasClass('zoom')) {
                                buttonClass = '.zoom';
                            }
                            $(graph).closest('.graph_container')
                                    .find(buttonClass)
                                    .addClass('selected');
                        });
        });
    });

    // Initialize the data for any graphs already on the page
    ajaxcall = [];
    $('.graph').each(function (index, element) {
        var hostname = $($(element).children('.graph_hostname')).attr('id');
        var servicename = $($(element).children('.graph_service_name')).attr('id');
        ajaxcall.push({
            "host" : hostname,
            "service" : servicename,
        });
    });
    ajaxcall = JSON.stringify(ajaxcall);
    $.ajax({
        dataType: 'json',
        url: '/railroad/graphs?graphs=' + ajaxcall,
        success: function (data, textStatus, XMLHttpRequest) {
            for (var i=0; i < data.length; i++) {
                var element = $('#{0}'.format(data[i]['slug']));
                drawGraph(element, data[i]);
            }
        },
        error: function (XMLHttpRequest, textStatus, error) {
            alert ("There was an error preloading the graphs");
        }
    });

    /**** CONFIGURATOR SETUP ****/
	// TODO: delete remnants (most of it) carefully!

    $('#debug_check').prop('checked', localStorageGet('debug'));
    updateDebug();

    $('#debug_check').change(function () {
        localStorageSet('debug', $('#debug_check').prop('checked'));
        updateDebug();
    });

    $('#debug a').live('click', function() {
        localStorageClear();
    });


    /*** Persistent form settings ***/
    // Anything in #configurator with a class of "... persist ..." will get persistence.
    $('#configurator').change(function() {
        var store = {};
        var value = null;
        $(this).find('.persist').each(function() {
            if ($(this).is('input')) {
                if ($(this).attr('type') == 'checkbox') {
                    value = $(this).prop('checked');
                } else if ($(this).attr('type') == 'radio') {
                    value = $(this).prop('checked');
                }
            } else if ($(this).is('select')) {
                value = $(this).val();
            }

            if (value != null) {
                store[$(this).attr('id')] = value;
            }
        });
        localStorageSet('form_configurator', store);
    });

    // Restore persisted objects
    var form_store = localStorageGet('form_configurator');
    for (key in form_store) {
        element = $('#configurator').find('#' + key);
        if ($(element).is('input')) {
            if ($(element).attr('type') == 'checkbox') {
                $(element).prop('checked', form_store[key]);
            } else if ($(element).attr('type') == 'radio') {
                $(element).prop('checked', form_store[key]);
            }
        } else if ($(element).is('select')) {
            $(element).val(form_store[key]);
        }
    }

    // Autocomplete anything with class = "... autocomplete ..."
    $('.autocomplete').each(function () { 
        $(this).autocomplete ( { source : "/railroad/ajax/autocomplete/" + $(this).attr('name' ), minLength : 1, autoFocus: true})
    });

    $('#cleargraphs').click(function () {
        $('.service_row').remove();
        $('#configurator').data('changed', true);
    });
    
    $('#clearform').bind('click', function () {
        $('#host').val("");
        $('#group').val("");
        $('#service').val("");
    });

    // Handle configurator form submissions
    $('#configurator').submit(function() {

        $('#cleargraphs').after('<img id="loading" src="/railroad-static/img/loading.gif" />');
        fields = $('#configurator').formSerialize();
        var ajaxmanager = $.manageAjax.create('configurator', {
            queue: true,
            maxRequests: 3,
        });
        ajaxmanager.add({
            data: fields,
            dataType: 'json',
            url: '/railroad/graphs',
            success: function(data, textStatus, XMLHttpRequest) {
                //reset_fields();
                $('#clearform').trigger('click');
                createGraphs(data);
                $('#loading').remove();
                //sortGraphs();
            },
            error: function(XMLHttpRequest, textStatus, errorThrown) {
                // TODO: Indicate error somehow, probably
            }
        });
        $('#configurator').data('changed', true);
        // Prevent normal form submission
        return false;
    });

    // *************************** Row manip ***************************
    // Expand all/of type buttons
    $('#expansion_by_type').find('input').bind('change', function() {
        auto_expansion();
        if (! $(this).prop('checked')) {
            $('#expandall').prop('checked', false);
        } else if ($(this).parent().siblings().children('input').not(':checked').length == 0) {
            // If all inputs are checked
            $('#expandall').prop('checked', true);
        }
    });

    $('#expandall').change(function() {
        var state = $(this).prop('checked');
        $('#expansion_by_type input').prop('checked', state);
        auto_expansion();
    });

    // expand one buttons
    $('.collapse_row').live('click', function() {
        collapse_row($(this).parents().parents().first());
    });
    $('.expand_row').live('click', function() {
        expand_row($(this).parents().parents().first());
    });
    // remove 1 buttons
    $('.remove_row').live('click', function() {
        var tr = $(this).parents().parents().first();
        tr.hide(animate_time, function() {
            $(tr).remove();
        });
    });

    // Handle configurator link generation
    $('#static').click(function() {
        function paint_link(data) {
            $('#link').html('Link: <input type="text" name="link"' +
                            ' readonly value="' + data + '" size="25" />');
            $('#link input').focus()
                            .select();
        }

        // If there are any service rows, we have a custom link to generate
        if($('.service_row').size()) {
            services = new Array();
            $('.service_row').each(function(index, element) {
                temp = $(element).find('.service_data').attr('href').split('/');
                host = temp[0];
                service = temp[1];
                start = $(element).find('.graph').data('start');
                end = $(element).find('.graph').data('end');
                services[index] = [host, service, start, end];
            });
            data = {services: services};
            $.ajaxq("linkgenerator",{
                data: data,
                dataType: 'json',
                type: 'POST',
                url: '/railroad/configurator/generatelink',
                success: function(data) {
                    paint_link(data);
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    // TODO: Handle error?
                }
            });
        // If not, give a link to the page
        } else {
             paint_link(window.location);
        } 
    });

    // Handle configurator link generation
    $('#live').click(function() {
        function paint_link(data) {
            $('#link').html('Link: <input type="text" name="link"' +
                            ' readonly value="' + data + '" size="25" />');
            $('#link input').focus()
                            .select();
        }

        // If anything on the page has changed, give them a link to that exact
        // zoom, configuration, etc
        if($('#configurator').data('changed')) {
            services = new Array();
            $('.service_row').each(function(index, element) {
                temp = $(element).find('.service_data').attr('href').split('/');
                host = temp[0];
                service = temp[1];
                if($(element).find('.graph').data('start')) {
                    start = -1;
                } else {
                    start = null;
                }
                if($(element).find('.graph').data('end')) {
                    end = -1;
                } else {
                    end = null;
                }

                services[index] = [host, service, start, end];
            });
            data = {services: services};
            $.ajaxq("linkgenerator",{
                data: data,
                dataType: 'json',
                type: 'POST',
                url: '/railroad/configurator/generatelink',
                success: function(data) {
                    paint_link(data);
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    // TODO: Handle error?
                }
            });
        // If not, give them a generic link to this page
        } else {
            paint_link(window.location);
        }
    });

    // Start the AJAX graph refreshes
    setTimeout(autoFetchDataNew, 600 * 1000);

    /******* Hint System *******/
    $('.hint').append('<span class="hide_hint"></span>');

    $('.hint .hide_hint').bind('click',
        function() {
            var hint_id = $(this).parent().attr('id');
            var hints_hidden = localStorageGet('hints_hidden');
            if (hints_hidden == null) {
                hints_hidden = {};
            }
            hints_hidden[hint_id] = true;
            localStorageSet('hints_hidden', hints_hidden);
            $(this).parent().remove();
        });

    var hints_hidden = localStorageGet('hints_hidden');
    if (hints_hidden == null) {
        hints_hidden = {};
    }
    $('.hint').each(function() {
        if (! hints_hidden[$(this).attr('id')]) {
            $(this).css('display', 'block');
        }
    });

    /******** Sorting *********/
    $('#sortby').bind('change', sortGraphs);
    $('#reverse_sort').bind('change', sortGraphs);
});

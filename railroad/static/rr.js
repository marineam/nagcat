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
        checked = " checked";
    }

    var stats = "";
    try {
        stats = ' (Cur: {0}, Max: {1}, Min: {2}, Avg: {3})'.format(
            series.statistics.cur.toPrecision(4), series.statistics.max.toPrecision(4),
            series.statistics.min.toPrecision(4), series.statistics.avg.toPrecision(4));
    } catch(e) {
        // graph doesn't have cur,max,min,avg, so skip them.
    }

    var out = '<input type="checkbox" id="{0}" class="removeSeries"{1}>{0}{2}</input>'.format(label, checked, stats);

    return out;
}

/******* GRAPH GENERATION/MANIPULTION *******/

// Takes the raw data and sets up required Flot formatting options
function formatGraph(element, data) {
    base = data.base;

    var first = true;
    var max = null;
    for (var i=0; i < data.data.length; i++) {
        if ( data.data[i].lines) {
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

            // Now fill in the graphs.
            for (var i=0; i < data.length; i++) {
                var element;
                if ( $('.{0}'.format(data[i]['slug'])).length > 1) {
                    element = $('.{0}#{1}'.format(data[i]['slug'], data[i]['uniq']))
                } else {
                    element = $('.{0}'.format(data[i]['slug']));
                }
                element.data('host', data[i]['host']);
                element.data('service', data[i]['service']);
                if (data[i].data) {
                    for (var j=0; j< data[i].data.length; j++) {
                        if ( data[i].data[j].label) {
                            if (data[i].data[j].lines) {
                                data[i].data[j].lines.show = true;
                            } else {
                                data[i].data[j].lines = { "show" : true };
                            }
                        }
                    }
                    drawGraph(element, data[i]);
                }
            }
            // get the graphs collapsed/expanded as they should be.
            auto_expansion();
        },
        error: function() {
            console.error('failed to get graph html');
        }
    });
}

// Plots the data in the given element
function drawGraph (elemGraph, data) {
    for (var i=0; i < data.data.length; i++) {
        if ( data.data[i].label) {
            if ( data.data[i].lines ) {
                data.data[i].lines.show = true;
            } else {
                data.data[i].lines = { "show" : true };
            }
        }
    }
    redrawGraph(elemGraph, data)
    collapse_or_expand($(elemGraph).closest('.service_row'));
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
            graphs = $(elemGraph);
        }
        graphs_to_update = [];
        graphs.each(function(index, element) {
            graph = {};
            // If there aren't enought data points, get MOAR DATA!
            graph = {
                "host" : $(element).data('host'),
                "service" : $(element).data('service'),
                "start" : parseInt(ranges.xaxis.from / 1000),
                "end" : parseInt(ranges.xaxis.to / 1000),
                "uniq": parseInt($(element).attr('id')),
            };
            graphs_to_update.push(graph);
        });
        // If there are graphs we need new data for, fetch new data!
        if ( graphs_to_update.length > 0 ) {
            ajaxcall = JSON.stringify(graphs_to_update);
            $.ajax ({
                url: '/railroad/graphs?graphs=' + ajaxcall,
                dataType: 'json',
                success: function (data, textStatus, XMLHttpRequest) {
                    for (var i=0; i < data.length; i++) {
                        for (var j=0; j < data[i].data.length; j++) {
                            if ( data[i].data[j].label ) {
                                if ( data[i].data[j].lines ) {
                                    data[i].data[j].lines.show = true;
                                } else {
                                    data[i].data[j].lines = { "show": true };
                                }
                            }
                        }
                        if (data[i].data) {
                            elemGraph = $('.{0}'.format(data[i]['slug']));
                            redrawGraph(elemGraph, data[i]);
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
            redrawGraph(elemGraph, data);
        }
    });

    var datePickers = $(elemGraph).siblings('.daterange').children('input').datepicker({
        onClose: function(selectedDate) {
            updateZoom(datePickers[0], datePickers[1]);
        },
        changeMonth: true,
        changeYear: true,
        maxDate : "+0d",
        minDate : "-5y",
        onSelect: function ( selectedDate ) {
           var option = this.name == "from" ? "minDate" : "MaxDate",
           instance = $(this).data('datepicker'),
           date = $.datepicker.parseDate(
                               instance.settings.dateFormat ||
                               $.datepicker._defaults.dateFormat,
                               selectedDate, instance.settings );
           datePickers.not(this).datepicker("option", option, date);
        },
    });
    $(datePickers[0]).datepicker('setDate', elemGraph.data('start'));
    $(datePickers[1]).datepicker('setDate', elemGraph.data('end'));
}

function redrawGraph(element, data) {
    data = formatGraph(element, data);
    $(element).data('plot', $.plot($(element), data.data, data.options));
    $(element).data('data', data);
    $(element).data('start', data.start);
    $(element).data('end', data.end);
    $(element).data('host', data.host);
    $(element).data('service', data.service);
}

function updateZoom(from, to) {
    var start = $(from).datepicker('getDate').getTime();
    var end = $(to).datepicker('getDate').getTime() + (24 * 60 * 60 * 100);

    var graph = $(from).parent().siblings('.graph').first();
    $(graph).trigger('plotselected', {'xaxis': {'from': start, 'to': end}});
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

}

// Automatically fetch new data for graphs that have the class 'ajax'
function autoFetchData() {
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
                var element = $('.{0}'.format(data[i]['slug']));
                if (data[i].data) {
                    drawGraph(element, data[i]);
                }
            }
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            alert ("Auto Fetch data failed");
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
//    "Hello {0}, how are you this fine {1}?".format(user_name, time_of_day);
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
    container.children().hide();
    if (container.children('.graph').length > 0) {
        container.append('<p class="graphcollapsed">Graph Collapsed</p>');
    }
    $(row).children('.status_text').children('p').hide();
    $(row).children('.status_text').children('h2').css({'display': 'inline'});

    // change the button to expand
    $(row).children('.controls').children('div.collapse_row').addClass('expand_row');
    $(row).children('.controls').children('div.collapse_row').removeClass('collapse_row');
}
function expand_row(row) {
    // Hide the graph and status text
    $(row).children('.graph_container').children('.graphcollapsed').remove();
    $(row).children('.graph_container').children().show();
    $(row).children('.status_text').children('p').show();
    $(row).children('.status_text').children('h2').css({'display': 'block'});

    // change the button to expand
    $(row).children('.controls').children('div.expand_row').addClass('collapse_row');
    $(row).children('.controls').children('div.expand_row').removeClass('expand_row');
}



// Execute setup code when page loads
$(document).ready(function() {
    /******* AJAX Helpers ******/
    $('body').ajaxStart(function() {
        console.log('found an ajax!');
        if ($('#cursor').length == 0) {
            $('body').append('<img id="cursor" src="/railroad-static/img/loading.gif" style="position: absolute;"/>');
            $('body').mousemove(function(e) {
                $('#cursor').css('top', e.clientY).css('left', e.clientX+7);
            });
            $('body').trigger('mousemove');
        }
    });

    $('body').ajaxStop(function() {
        $('#cursor').remove();
    });

    /**** GRAPH SETUP ****/

    // Bind the graph time range selection buttons
    $('.options input[type=button]').live('click', function() {
        var dates = $(this).parent().siblings('.daterange');

        if ($('#sync').prop('checked')) {
            var from = $('input[name=from]');
            var to = $('input[name=to]');
        } else {
            var from = $(dates).children('[name=from]');
            var to = $(dates).children('[name=to]');
        }

        to.datepicker('setDate', new Date());
        from.datepicker('setDate', new Date());

        if ($(this).attr('name') == 'week') {
            from.datepicker('setDate', '-1w');
        } else if ($(this).attr('name') == 'month') {
            from.datepicker('setDate', '-1m');
        } else if ($(this).attr('name') == 'year') {
            from.datepicker('setDate', '-1y');
        }

        to.datepicker('refresh')
        from.datepicker('refresh')
        updateZoom(from,to);
    });

    // Initialize the data for any graphs already on the page
    ajaxcall = [];
    $('.graph').each(function (index, element) {
        var slug = $(element).attr('name');
        graphs = $('.{0}'.format(slug)).each(function (index, element) {
            $(element).attr('id', index);
        });
        var hostname = $($(element).children('.graph_hostname')).attr('id');
        var servicename = $($(element).children('.graph_service_name')).attr('id');
        var start = $($(element).children('.graph_start')).attr('id');
        var end = $($(element).children('.graph_end')).attr('id');
        var uniq = $(element).attr('id');
        ajaxcall.push({
            "host" : hostname,
            "service" : servicename,
            "uniq" : uniq, // This is used to identify graphs if there are multiples of the same
                           // host and service combination (like on the service page).
            "start" : start,
            "end" : end,
        });
    });
    ajaxcall = JSON.stringify(ajaxcall);
    $.ajax({
        dataType: 'json',
        url: '/railroad/graphs?graphs=' + ajaxcall,
        success: function (data, textStatus, XMLHttpRequest) {
            for (var i=0; i < data.length; i++) {
                var element;
                if (data[i]['uniq']) {
                    element = $('.{0}#{1}'.format(data[i]['slug'],data[i]['uniq']));
                } else {
                    element = $('.{0}'.format(data[i]['slug']));
                }
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

    $('#localtime, #utc').bind('change', function() {
        graphs = $('.graph');
        graphs.each(function(index, element) {
            if (element.data('data')) {
                redrawGraph(element, $(element).data('data'));
            }
        });
    });

    // Handle configurator form submissions
    $('#configurator').submit(function() {

        fields = $('#configurator').formSerialize();
        $.ajax({
            data: fields,
            dataType: 'json',
            url: '/railroad/graphs',
            success: function(data, textStatus, XMLHttpRequest) {
                //reset_fields();
                $('#clearform').trigger('click');
                createGraphs(data);
                //sortGraphs();
            },
            error: function(XMLHttpRequest, textStatus, errorThrown) {
                // TODO: Indicate error somehow, probably
            }
        });
        $('#configurator').data('changed', true);
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
        tr.hide(0, function() {
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
    setTimeout(autoFetchData, 600 * 1000);

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

    $('#hide_all_hints').change(function () {
        var hints_hidden = localStorageGet('hints_hidden');
        if (!hints_hidden) {
            hints_hidden = {};
        }
        hints_hidden['hide_all_hints'] = $(this).prop('checked');
        localStorageSet('hints_hidden', hints_hidden);
        if ($(this).prop('checked')) {
            var hints = $('.hint .hide_hint');
            hints.each(function (index,element) {
                $(element).trigger('click');
            });
        }
    });



    var hints_hidden = localStorageGet('hints_hidden');
    if (hints_hidden == null) {
        hints_hidden = {};
    }
    $('.hint').each(function() {
        if (! hints_hidden[$(this).attr('id')] && ! hints_hidden["hide_all_hints"]) {
            $(this).css('display', 'block');
        }
    });

    /******** Sorting *********/
    $('#sortby').bind('change', sortGraphs);
    $('#reverse_sort').bind('change', sortGraphs);

});

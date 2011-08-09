/*
 * Copyright 2011 ITA Software, Inc.
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

/* This file should be for function definitions only, there should be no side
 * effects from running this file. */

/* Remove all elements in a list for which func(e) is true in O(n) time
 * (assuming func runs in O(1) */
Array.prototype.removeMatching = function(func) {
    var arr = this;
    var i = 0;
    var offset=0;
    while (i+offset < arr.length) {
        if (offset > 0) {
            arr[i] = arr[i+offset];
        }
        if (func(arr[i])) {
            offset += 1;
            arr[i] = arr[i+offset];
        } else {
            i += 1;
        }
    }
    arr.length -= offset;
    return arr.length;
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

/********** Form Persistence **********/

/* Save the state of the given form into localstorage. */
function saveFormPersistence(elemPersist) {
    var store = {};
    var value = null;
    $(elemPersist).find('.persist').each(function(index, element) {
        if ($(element).is('input')) {
            if ($(element).attr('type') === 'checkbox') {
                value = $(element).prop('checked');
            } else if ($(element).attr('type') === 'radio') {
                value = $(element).prop('checked');
            } else if ($(element).attr('type') === 'field') {
                value = $(element).val();
            }
        } else if ($(element).is('select')) {
            value = $(element).val();
        }

        if (value != null) {
            store[$(element).attr('id')] = value;
        }
    });
    var dictName = $(elemPersist).attr('id')
    localStorageSet(dictName, store)
}

/* Restore the state of the given form from localstorage. */
function restoreFormPersistence(elemPersist) {
    var form_store = localStorageGet($(elemPersist).attr('id'));
    for (key in form_store) {
        element = $(elemPersist).find('#' + key);
        if ($(element).is('input')) {
            if ($(element).attr('type') === 'checkbox') {
                $(element).prop('checked', form_store[key]);
            } else if ($(element).attr('type') === 'radio') {
                $(element).prop('checked', form_store[key]);
            } else if ($(element).attr('type') === 'field') {
                $(element).val(form_store[key]);
            }
        } else if ($(element).is('select')) {
            $(element).val(form_store[key]);
        }
    }
}

/* Bind a menu div to a button's on click event. */
var bindMenu = function(button, menu) {
    var pos = $(button).offset();
    var height = $(button).height();
    $(menu).position({my: 'left top', at: 'left bottom', of: $(button)}).hide();
    $(button).bind('click', function() {
        $(menu).toggle();
    });
}

/* Update the all graphs check box to match the service row checkboxes. */
function allChecked(func) {
    $('.service_row').each(function(index, elem) {
        if ($(elem).children('.controls').children('input').prop('checked')) {
            func(elem);
        }
    });
    $('.service_row .controls input[type=checkbox]').prop('checked', false);
    $('#checkall input').prop('checked', false);
}

/* Call getData for every graph on the page (as one call) */
function getAllData(callback) {
    var sos = [];
    var meta = $('#graphs').data('meta');
    for (var i=0; i<meta.length; i++) {
        var so = meta[i];
        if (!so['data']) {
            sos.push({
                'host': so['host'],
                'service': so['service'],
                'start': so['start'],
                'end': so['end'],
            });
        }
    }
    if (sos.length) {
        getData(sos, callback);
    } else {
        callback([]);
    }
}


// Sort the graphs.
/* Return a function that is the opposite of a given comparer */
function reverse(func) {
    var f = function(a,b) {
        return func(b,a);
    }
    f.usesData = func.usesData;
    return f;
}
/* Give a function that returns a value from an element, make a function that
 * compares two elements based on that value. */
function makeComparer(val) {
    var f = function(a, b) {
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
    f.usesData = false;
    return f;
}
/* The different ways to sort the graphs. */
var sorts = {
    'service': makeComparer(function(so) {
        var s = so['service'].toLowerCase().trim();
        console.log(s);
        return s;
    }),
    'host': makeComparer(function(so) {
        return so['host'].toLowerCase().trim();
    }),
    'status': reverse(makeComparer(function(so) {
        return so['state'];
    })),
    'duration': makeComparer(function(so) {
        return so['duration'];
    })
}

/* Do the sorting. */
function sortGraphs(name, reversed) {
    var sorter = sorts[name];
    if (reversed) {
        sorter = reverse(sorter);
    }

    var finishSort = function() {
        var meta = $('#graphs').data('meta');
        meta.sort(sorter);
        $('graphs').data('meta', meta);
        selectServiceObjs();
    }

    if (sorter.usesData) {
        getAllData(finishSort);
    } else {
        finishSort();
    }
}

/* Triggered when the preference panel has been closed. Update the page if
 * needed. */
function redrawOnClosePreference() {
    if ($('#preference_panel').data('changed') && $('.service_row').length > 0) {
        var meta = $('#graphs').data('meta');
        if (meta) {
            for (var i=0; i < meta.length; i++) {
                meta[i].data = null;
                meta[i].isGraphed = false;
            }
            selectServiceObjs();
        }
        $('#preference_panel').data('changed', null);
    }
}

/* Get petPage from local storage, with a default value. */
function getPerPage() {
    var perpage = 25;
    if (localStorageGet('preference_panel')) {
        if (localStorageGet('preference_panel')['graphsPerPage']) {
            perpage = localStorageGet('preference_panel')['graphsPerPage'];
            perpage = parseInt(perpage);
        }
    }
    return perpage;
}

function makeDatetimePicker(elem, date, onClose) {
    var tz;
    if ($('#localtime').prop('checked')) {
        tz = getTimezoneString(new Date());
    } else  {
        tz = '+0000';
        var offset = new Date().getTimezoneOffset();
        if (date) {
            date.add({minutes: offset});
        }
    }
    var datePicker = $(elem).datetimepicker({
        timeFormat: 'hh:mm z',
        timezoneList: [tz],
        onClose: onClose,
        changeMonth: true,
        changeYear: true,
    });
    if (date) {
        $(datePicker).datetimepicker('setDate', date)
    }
    return datePicker;
}

function setupGraph(metadata) {
    if (!!metadata.onPage) {
        $(metadata.jQueryElement).show();
        // JQuery is smart. If we add an element already on the page it moves
        // it to where we put.
        $(metadata.jQueryElement).appendTo('#graphs');
    } else {
        $(metadata.jQueryElement).appendTo('#graphs');
        metadata.onPage = true;
    }
    var elemGraph = $('.{0}'.format(metadata.slug));
    var elemGraphDates = $(elemGraph).siblings('.daterange')
        .children('input');

    var startDate = new Date(metadata.start * 1000);
    var endDate = new Date(metadata.end * 1000);

    var datePickers = [];
    var callBack = function() {
        var graph = $(datePickers[0]).parent().siblings('.graph').first();
        var fromDate = $(datePickers[0]).datetimepicker('getDate');
        var toDate = $(datePickers[1]).datetimepicker('getDate');
        updateZoom(graph, fromDate, toDate);
    };
    datePickers[0] = makeDatetimePicker($(elemGraphDates).first(),
        startDate, callBack);
    datePickers[1] = makeDatetimePicker($(elemGraphDates).last(),
        endDate, callBack);

    $(elemGraph).siblings('.graphloading').remove();
}

/* Data and graph manipulation and loading */
function selectServiceObjs() {
    var meta = $('#graphs').data('meta');

    var perpage = getPerPage();
    var start = $('#graphs').data('start');
    if (!start || start <= 0) {
        start = 1;
        $('#graphs').data('start', start);
    }

    var end = Math.min(start+perpage-1, meta.length);

    $('.service_row').each(function (index, element) {
        for (var i=0; i< meta.length; i++) {
            if ($(element).find('.graphInfo').attr('name') == meta[i].slug) {
                meta[i].jQueryData = $(element).find('.graphInfo').data();
            }
        }
    });

    $('.service_row').hide();
    for (var i=0; i<meta.length; i++) {
        if (!meta[i].jQueryElement) {
            meta[i].jQueryElement = $(meta[i].html);
        }
    }

    for (var i=start-1; i<end; i++) {
        setupGraph(meta[i]);
    }
    update_number_graphs();
    drawSO();
    auto_expansion();

    var totalpages = Math.floor(meta.length / perpage);
    $('#graphs').data('totalpages', totalpages);
    var totalgraphs = meta.length
    $('#totalgraphs').text(meta.length);
    $('#firstgraph').text(start);
    $('#lastgraph').text(Math.min(totalgraphs, (end)));
    $('#totalgraphs').text(totalgraphs);

    var prevItem = null;
    $('.graph').parent().bind('plothover', function(event, pos, item) {
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
    $('.graph').parent().bind('plotselected', function (event, ranges) {
        var elemGraph = $(this).children('.graph');
        var meta = $('#graphs').data('meta');
        graphs_to_update = [];
        if ($('#sync').prop('checked')) {
            for (var i=0; i < meta.length; i++) {
                graphs_to_update.push(meta[i]);
            }
        } else {
            for (var i=0; i< meta.length; i++) {
                if (meta[i].slug === $(elemGraph).attr('name')) {
                    graphs_to_update.push(meta[i]);
                }
            }
        }
        for (var i=0; i < graphs_to_update.length; i++) {
            if (graphs_to_update[i]['isGraphable']) {
                graphs_to_update[i]['start'] = parseInt(ranges.xaxis.from / 1000);
                graphs_to_update[i]['end'] = parseInt(ranges.xaxis.to / 1000);
                graphs_to_update[i]['isGraphed'] = false;
            }
        }
        drawSO();
    });

    if (end >= totalgraphs) {
        $('#nextpage').data('enabled', false).css({'opacity': 0.25});
        $('#nextpage .sprite').removeClass('hover');
    } else {
        $('#nextpage').data('enabled', true).css({'opacity': 1.0});
        $('#nextpage .sprite').addClass('hover');
    }
    if (start <= 1) {
        $('#prevpage').data('enabled', false).css({'opacity': 0.25});
        $('#prevpage .sprite').removeClass('hover');
    } else {
        $('#prevpage').data('enabled', true).css({'opacity': 1.0});
        $('#prevpage .sprite').addClass('hover');
    }

    if (meta.length === 0 ) {
        $('#pages').hide();
    } else {
        $('#pages').show();
    }

}

/* Make an ajax call to get new data, then call the callBack. */
function getData(ajaxData, callBack) {
    ajaxData = JSON.stringify(ajaxData);
    $.ajax({
        url: '/railroad/graphs',
        data: {graphs: ajaxData},
        type: 'POST',
        async: true,
        dataType: 'json',
        success: function (data, textStatus, XMLHttpRequest) {
            var meta = $('#graphs').data('meta');
            for (var i=0; i < data.length; i++) {
                for (var j=0; j < meta.length; j++) {
                    if (data[i].slug === meta[j].slug) {
                        if (meta[j].data) {
                            data[i] = compareData(meta[j].data, data[i]);
                        }
                        meta[j].data = data[i];
                    }
                }
            }
            callBack(data);
        },
        error: function () {
            console.log('There was an error in obtaining the data for graphs');
        }
    });
}

/* Draw a service object. */
function drawSO() {
    var perpage = getPerPage();
    var begin = $('#graphs').data('start');
    if (!begin || begin <= 0) {
        begin = 1;
        $('#graphs').data('starte', begin);
    }
    var meta = $('#graphs').data('meta');
    var stop = Math.min(begin+perpage-1, meta.length);
    var servicesToGraph = [];
    for (var i=begin-1; i<stop; i++) {
        if (meta[i].isGraphable) {
            if (!meta[i].data || ! meta[i].isGraphed) {
                var host = meta[i].host;
                var service = meta[i].service;
                if (meta[i].isGraphable) {
                    var start = meta[i].start;
                    var end = meta[i].end;
                } else {
                    var start = 0;
                    var end = 0;
                }
                var serviceDict = {
                    'host': host,
                    'service': service,
                    'start': start,
                    'end': end,
                };
                servicesToGraph.push(serviceDict);
            }
        }
    }
    if (servicesToGraph.length > 0) {
        getData(servicesToGraph, function(data) {
            var meta = $('#graphs').data('meta');
            for (var i=0; i<meta.length; i++) {
                var elem = $('.graph.' + meta[i]['slug']);
                // If the graph is on the page
                if (elem.length > 0) {
                    if (meta[i].data) {
                        if (!meta[i].isGraphed) {
                            drawGraph(elem, meta[i].data);
                            meta[i].isGraphed = true;
                        }
                    } else {
                        $(elem).data('host', meta[i].host);
                        $(elem).data('service', meta[i].service);
                    }
                }
            }
        });
    }
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

    $('.removeSeries').live('click', function() {
        var meta = $('#graphs').data('meta');
        var metaIndex = -1;
        var elemGraph = $(this).closest('.legend').siblings('.graph');
        for (var i=0; i <meta.length; i++) {
            if (  meta[i].slug === $(elemGraph).attr('name')) {
                metaIndex = i;
                break;
            }
        }
        if (!meta[metaIndex]) {
            // The graph must have been removed. Fugettaboutit
            return
        }
        if (meta[metaIndex].data) {
            data = meta[metaIndex].data;
            for (var i=0; i < data.data.length; i++) {
                if (data.data[i].label == $(this).attr('id')) {
                    data.data[i]['lines']['show'] ^= true; // toggle
                }
            }
            redrawGraph(elemGraph, data);
        }
    });

    $(elemGraph).siblings('.graphloading').remove();
}

/* Redraw a graph. */
function redrawGraph(element, data) {
    var meta = $('#graphs').data('meta');
    var metaIndex;
    for (var i=0; i < meta.length; i++) {
        if (meta[i].slug === data.slug) {
            metaIndex = i;
            break;
        }
    }
    if (!meta[metaIndex]) {
        // The graph must have been removed. Fugettaboutit
        return
    }
    data = formatGraph(element, data);
    meta[metaIndex].data = data;
    $(element).data('plot', $.plot($(element), data.data, data.options));
    $(element).siblings('.graphloading').text('Rendering Graph...');

    $(element).data('data', data);
    $(element).data('start', data.start);
    $(element).data('end', data.end);
    $(element).data('host', data.host);
    $(element).data('service', data.service);
    //meta[metaIndex].jQueryElement = $(element).closest('.service_row');
}

/* Gets a timezoneString that looks like '-0400' from a datetime. */
function getTimezoneString(date) {
    var timezoneString = (date.getTimezoneOffset() / -60);
    var sign = '';
    if (timezoneString > 0) {
        sign = '+';
    } else if (timezoneString < 0) {
        sign = '-';
    }
    if (Math.abs(timezoneString) < 10) {
        timezoneString = '{0}0{1}00'.format(sign, Math.abs(timezoneString));
    } else {
        timezoneString = '{0}{1}00'.format(sign, Math.abs(timezoneString));
    }
    return timezoneString;
}

/* Return a pretty version of a number. Probably for graph labels. */
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

    /* This is really the best way to get no more than 2 digits of precision. */
    var n = Math.round(n * 100) / 100;
    return '{0}{1}'.format(n, labels[label_index]);
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

    var out = ('<input type="checkbox" id="{0}" class="removeSeries"{1}/>' +
               '{0}{2}').format(label, checked, stats);

    return out;
}

/* Generate the state of the page for permalinks */
function generateState() {
    var meta = $('#graphs').data('meta');
    for (var i=0; i < meta.length; i++) {
        meta[i].data = null;
        meta[i].jQueryElement = null;
    }
    return JSON.stringify(meta);
}

/* Update the number of graphs hidden on this page. */
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

/* Update the number of graphs. */
function update_number_graphs() {
    var state_ok_count = 0;
    var state_warning_count = 0;
    var state_critical_count = 0;
    var state_unknown_count = 0;
    var states = [state_ok_count, state_warning_count,
        state_critical_count, state_unknown_count];
    var meta = $('#graphs').data('meta');
    if (meta) {
        for (var i=0; i < meta.length; i++) {
            if (meta[i].state) {
                states[meta[i].state]++;
            }
        }
        $('#stats #service_count').html('{0} Services'.format(
            meta.length));
        $('#stats .state_ok').html('{0}'.format(
            states[0]));
        $('#stats .state_warning').html('{0}'.format(
            states[1]));
        $('#stats .state_critical').html('{0}'.format(
            states[2]));
        $('#stats .state_unknown').html('{0}'.format(
            states[3]));
    }
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
        if ($(container).children('p').length < 1) {
            container.append('<p class="graphcollapsed">Graph Collapsed</p>');
        }
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

/******* Local Storage Hooks *******/
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
        return true;
    }
    return false;
}

/* Parse data out of the html of a service row. */
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

function compareData(oldData, newData) {
    /* This function, given a set of old data, and new data,
     * will make sure that all of the data lines in the old and new
     * have matching  show attributes
     */
    if (oldData.host === newData.host) {
        if (oldData.service === newData.service) {
            for (var i=0; i < oldData.data.length; i++) {
                for (var j=0; j < newData.data.length; j++) {
                    if (oldData.data[i].label === newData.data[j].label) {
                        newData.data[j].lines = oldData.data[i].lines
                        break;
                    }
                }
            }
        }
    }
    return newData;
}

// Automatically fetch new data for graphs.
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

/* Change the zoom of a graph to the given date range. */
function updateZoom(graph, from, to) {
    $(graph).trigger('plotselected', {'xaxis': {'from': from, 'to': to}});
}

/* Show a fake tooltip near x,y. */
function showTooltip(x, y, label) {
    $('#tooltip').remove()
    $('<div id="tooltip">{0}</div>'.format(label)).appendTo('body')
        .css({'left': x+5, 'top': y+5});
}

/* Get the metadata for a list of service objs. */
function getServiceObjs(ajaxData) {
    $.ajax({
        data: ajaxData,
        url: '/railroad/configurator/meta',
        type: 'POST',
        async: true,
        dataType: 'json',
        success: function (meta, textStatus, XMLHttpRequest) {
            $('#graphs').data('meta', meta);
            selectServiceObjs();
        },
        error: function () {
            console.log('failed to add graph html');
        }
    });
}

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

// TODO: Find a way to remove global variable?
base = 0;

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

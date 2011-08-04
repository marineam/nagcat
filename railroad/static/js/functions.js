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
    updateDebug();
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
function reverse(func) {
    var f = function(a,b) {
        return func(b,a);
    }
    f.usesData = func.usesData;
    return f;
}
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
var sorts = {
    'service': makeComparer(function(so) {
        return so['service'].toLowerCase().trim();
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

/* Data and graph manipulation and loading */
function selectServiceObjs() {
    var perpage;
    if (localStorageGet('preference_panel')) {
        if (localStorageGet('preference_panel')['graphsPerPage']) {
            perpage = localStorageGet('preference_panel')['graphsPerPage'];
            perpage = parseInt(perpage);
        }
    } else {
        perpage = 25;
    }
    var curpage = $('#graphs').data('curpage');
    if (!curpage) {
        curpage = 0;
        $('#graphs').data('curpage', 0);
    }

    var meta = $('#graphs').data('meta');
    var start = curpage * perpage;
    var end = Math.min(start+perpage, meta.length);

    $('.service_row').each(function (index, element) {
        for (var i=0; i< meta.length; i++) {
            if ($(element).find('.graphInfo').attr('name') == meta[i].slug) {
                meta[i].jQueryData = $(element).find('.graphInfo').data();
            }
        }
    });

    $('#graphs').html('');
    for (var i=0; i<meta.length; i++) {
        if (!meta[i].jQueryElement || !meta[i].data || !meta[i].isGraphed) {
            meta[i].jQueryElement = $(meta[i].html);
        }
    }

    for (var i=start; i<end; i++) {
        $(meta[i].jQueryElement).appendTo('#graphs');
        if (meta[i].jQueryData) {
            for (key in meta[i].jQueryData) {
                $('.{0}'.format(meta[i].slug)).data(key, meta[i].jQueryData[key]);
            }
        }
        var elemGraph = $('.{0}'.format(meta[i].slug));
        var elemGraphDates = $(elemGraph).siblings('.daterange').children('input');
        var datePickers = $(elemGraphDates).datetimepicker({
            onClose: function(selectedDate) {
                updateZoom($(datePickers[0]).parent().siblings('.graph').first(),
                           $(datePickers[0]).datetimepicker('getDate'),
                           $(datePickers[1]).datetimepicker('getDate'));
        var from = $(elemGraphDates)[0];
        var to = $(elemGraphDates)[1];
        var start = $(from).datetimepicker('getDate').getTime();
        var end = $(to).datetimepicker('getDate').getTime();
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
    update_number_graphs();
    drawSO();

    var totalpages = Math.floor(meta.length / perpage);
    $('#graphs').data('totalpages', totalpages);
    var totalgraphs = meta.length
    $('#totalgraphs').text(meta.length);
    $('#firstgraph').text(curpage * perpage + 1);
    $('#lastgraph').text(Math.min(totalgraphs, (curpage + 1) * perpage));
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
                graphs_to_update[i]['data'] = null;
                graphs_to_update[i]['isGraphed'] = false;
            }
        }
        drawSO();
    });

    if (curpage >= totalpages) {
        $('#nextpage').data('enabled', false).css({'opacity': 0.25});
        $('#nextpage .sprite').removeClass('hover');
    } else {
        $('#nextpage').data('enabled', true).css({'opacity': 1.0});
        $('#nextpage .sprite').addClass('hover');
    }
    if (curpage <= 0) {
        $('#prevpage').data('enabled', false).css({'opacity': 0.25});
        $('#prevpage .sprite').removeClass('hover');
    } else {
        $('#prevpage').data('enabled', true).css({'opacity': 1.0});
        $('#prevpage .sprite').addClass('hover');
    }

    if (!$('#prevpage').data('enabled') && !$('#nextpage').data('enabled')) {
        $('#pages').hide();
    } else {
        $('#pages').show();
    }

}

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

function drawSO() {
    var perpage;
    if (localStorageGet('preference_panel')) {
        if (localStorageGet('preference_panel')['graphsPerPage']) {
            perpage = localStorageGet('preference_panel')['graphsPerPage'];
        }
    } else {
        perpage = 25;
    }
    var curpage = $('#graphs').data('curpage');
    if (!curpage) {
        curpage = 0;
        $('#graphs').data('curpage', 0);
    }
    var meta = $('#graphs').data('meta');
    var begin = curpage * perpage;
    var stop = Math.min(begin+perpage, meta.length);
    var servicesToGraph = [];
    for (var i=begin; i<stop; i++) {
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

    $('.removeSeries').live('click', function () {
        var meta = $('#graphs').data('meta');
        var metaIndex;
        var elemGraph = $(this).closest('.legend').siblings('.graph');
        for (var i=0; i <meta.length; i++) {
            if (  meta[i].slug === $(elemGraph).attr('name')) {
                metaIndex = i;
                break;
            }
        }
        if (metaIndex) {
        if (meta[metaIndex].data) {
                data = meta[metaIndex].data;
                for (var i=0; i < data.data.length; i++) {
                    if (data.data[i].label == $(this).attr('id')) {
                        data.data[i]['lines']['show'] ^= true; // toggle
                    }
                }
                redrawGraph(elemGraph, data);
            }
        }
    });
    // elemGraphDates keeps the line below it < 80 chars
    var elemGraphDates = $(elemGraph).siblings('.daterange').children('input');
    var datePickers = $(elemGraphDates).datetimepicker({
        onClose: function(selectedDate) {
            updateZoom($(datePickers[0]).parent().siblings('.graph').first(),
                       $(datePickers[0]).datetimepicker('getDate'),
                       $(datePickers[1]).datetimepicker('getDate'));
    var from = $(elemGraphDates)[0];
    var to = $(elemGraphDates)[1];
    var start = $(from).datetimepicker('getDate').getTime();
    var end = $(to).datetimepicker('getDate').getTime();
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
    var meta = $('#graphs').data('meta');
    var metaIndex;
    for (var i=0; i < meta.length; i++) {
        if (meta[i].slug === data.slug) {
            metaIndex = i;
            break;
        }
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

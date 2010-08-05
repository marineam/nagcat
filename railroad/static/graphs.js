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

// Base for data manipulation
// TODO: A global variable? I hate you.
base = 0;

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

    // pretty rounding of base-10 numbers
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
    return label.replace(/_/g, ' ');
}

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

// Creates a graph
function createGraph(element, path, callback, zoom) {
    // If the graph isn't busy
    if(!$(element).data('busy')) {
        $(element).data('busy', true);
        $(element).append('<div class="throbber"></div>');
        $(element).remove('.empty');
        $.ajax({
            url: '/railroad/parserrd/' + path,
            dataType: 'json',
            success: function(data) {
                // If we are zooming and there's no data, just bail with an error
                if(zoom && data.empty) {
                    plot = $(element).data('plot');
                    plot.clearSelection();
                    $(element).append('<div class="error">no data to zoom</div>');
                    // Nice fadeOut won't let us remove the element, so use a callback
                    $(element).find('.error')
                              .delay(500)
                              .fadeOut(500,
                                       function() {
                                           $(this).remove();
                                       });
                } else {
                    data = formatGraph(element, data);
                    $(element).data('plot', $.plot($(element), data.data, data.options));
                    if(data.options.yaxis.label) {
                        $(element).before('<div class="ylabel"><span>' +
                                          data.options.yaxis.label +
                                          '</span></div>');
                    }
                    if(data.empty == true) {
                        $(element).append('<div class="empty">no data</div>');
                    }

                    update = $(element).closest('.graph_container')
                                       .find('.update');
                    update.html('updated: ' + data.current_time);

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
                    // Nice fadeOut won't let us remove the element, so use a callback
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
   
// Update an AJAX timestamp
function updateTimestamp(element) {
    // TODO: Format time cleaner?
    time = new Date();
    element.html('updated: ' + time.toString());
}

// Execute setup code when page loads
$(document).ready(function() {
    // Bind the graph time range selection buttons
    $('.options ul li').click(function() {
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
                            // This is pretty horrible, perhaps there is a better way
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
                            $(graph).closest('.graph_container').find(buttonClass).addClass('selected');
                        });      
        });
    });

    // Loop over the things to be graphed and produce graphs for each
    $(".graph").each(function(index, element) {

        // Store the graph data for usage later
        path = $(element).find('a').attr('href');
        splitPath = path.split('/');
        $(element).data('host', splitPath[0]);
        $(element).data('service', splitPath[1]);
        $(element).data('res', splitPath[4]);

        createGraph(element, path);

        // Allow for zooming
        $(element).bind('plotselected', function (event, ranges) {
            // The graph isn't busy anymore, allow updates
            $(element).data('busy', null); 

            // If we are supposed to sync the graphs, loop over all graphs
            if($('#sync').attr('checked')) {
                graphs = $('.graph');
                // Allow us to zoom even when it makes no sense if we are synced
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
                                zoomButton = $(element).closest('.graph_container')
                                                       .find('.zoom');
                                selected = $(element).closest('.graph_container')
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

    });

    // Bind ourselves to form submissions
/*    $('#configurator').ajaxForm({
        target: '#target',
        replaceTarget: true,
        success: function() {
            $('#configurator').remove();
            $(
        },
    });*/

    $('#configurator').data('types', new Array());

    $('#configurator').submit(function() {
        fields = $('#configurator').formSerialize();
        $.ajax({
            data: fields,
            dataType: 'html',
            url: $('#configurator').attr('action'),
            success: function(data, textStatus, XMLHttpRequest) {
                $('#configurator').before(data);
                $('#configurator').resetForm();
            }
        });
        // Prevent normal form submission
        return false;
    });

    // If we're on a configurator page, load the default state
    if($('#configurator') != undefined) {
        $.getJSON('/railroad/custom/formstate', function(data) {
            $('#configurator').data('state', data);
        });
    }

    $('.type').live('change', function() {
        id = parseInt($(this).attr('name').replace('type', ''));
        value = $('#value' + id);
        $(value).empty();
        state = $('#configurator').data('state');
        $.each(state[$(this).attr('value')], function(index, item) {
            $(value).append(new Option(item, item));
        });
    });

    $('.value').live('change', function() {
        // Read the current id and fetch a new one that is higher
        old_id = parseInt($(this).attr('name').replace('value', ''));
        id = old_id + 1;
        // If we have a valid value and few enough ids, insert a field
        if($(this).val()) {
            fields = $('#configurator').formSerialize();
            $.ajax({
                data: fields,
                dataType: 'json',
                url: '/railroad/custom/formstate',
                success: function(data, textStatus, XMLHttpRequest) {
                    $('#configurator').data('state', data);
                    // This is dumber than the dumbest dumb, but jQuery sucks at inserting 
                    $('#options').append('<select name="type' + id + '" class="type" id="type' + id + '"><option></option></select> <select name="value' + id + '" class="value" id="value' + id + '"></select><br />');
                    $.each(state['options'], function(index, item) {
                        $('#type' + id).append(new Option(item, item));
                    });
                    $('#type' + old_id).attr('disabled', 'disabled');
                }
            });
        }
    });

    $('#group').change(function() {
        $.ajax({
            url: '/railroad/selectgroup/' + $(this).val(),
            dataType: 'json',
            success: function(data) {
                $('#host').empty();
                $('#host').append(new Option('All Hosts', null));
                $.each(data['host_list'], function(index, item) {
                    $('#host').append(new Option(item, item));
                });
                $('#service').empty();
                $('#service').append(new Option('All Services', null));
                $.each(data['service_list'], function(index, item) {
                    $('#service').append(new Option(item, item));
                });
            }
        });
    });

    $('#host').change(function() {
        if(!$(this).val()) {
            $('#group').change();
        } else {
            $.ajax({
                url: '/railroad/selecthost/' + $(this).val(),
                dataType: 'json',
                success: function(data) {
                    $('#service').empty();
                    $('#service').append(new Option('All Services', null));
                    $.each(data['service_list'], function(index, item) {
                        $('#service').append(new Option(item, item));
                    });
                }
            });
        }
    });


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
    setTimeout(autoFetchData, 60 * 1000);

});


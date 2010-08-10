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

// Grabs the default state for the configurator
function default_state() {
    // If we're on a configurator page, load the default state
    if($('#configurator') != undefined) {
        $.getJSON('/railroad/configurator/formstate', function(data) {
            $('#configurator').data('state', data);
        });
    }
}

// Execute setup code when page loads
$(document).ready(function() {
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

    // Loop over the things to be graphed and produce graphs for each
    function parse_graphs(index, element) {

        // Don't set up graphs already set up
        $(element).addClass('setup');

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

    // Initialize the data for any graphs already on the page
    $(".graph").each(parse_graphs);

    // Handle configurator form submissions
    $('#configurator').submit(function() {
        $(this).append('<div class="throbber"></div>');
        // Enable the fields again so they can be submitted
        $('[id^=type]').attr('disabled', null);
        $('[id^=value]').attr('disabled', null);

        fields = $('#configurator').formSerialize();
        $.ajax({
            data: fields,
            dataType: 'html',
            url: $('#configurator').attr('action'),
            success: function(data, textStatus, XMLHttpRequest) {
                //reset_fields();
                $('#configurator').trigger('reset');
                // Add the new graph and setup the new graphs
                $('#graphs').append(data);
                $('.graph:not(.setup)').each(parse_graphs);
                $('#configurator').find('.throbber').remove();
            },
            error: function(XMLHttpRequest, textStatus, errorThrown) {
                // TODO: Indicate error somehow, probably
                $('#configurator').find('.throbber').remove();
            }
        });
        // Prevent normal form submission
        return false;
    });
   
    // Properly clear the form when someone attempts to reset it
    $('#configurator').bind('reset', function() {
        // Enable all fields
        $('[id^=type]').attr('disabled', null);
        $('[id^=value]').attr('disabled', null);
        // Disable Add button
        $('#submit').attr('disabled', 'disabled');
        // Remove added fields and empty the first value box 
        $('#options').empty();
        $('#value0').empty();
        // Get the default form state for values
        default_state();
    });
 
    // Load the default state for configurator
    default_state();

    // Automatically fill in the configurator value options when the type is
    // changed
    $('.type').live('change', function() {
        id = parseInt($(this).attr('name').replace('type', ''));
        value = $('#value' + id);
        $(value).empty();
        state = $('#configurator').data('state');
        $(value).append(new Option());
        value_name = $(this).attr('value').toLowerCase();
        $.each(state[value_name], function(index, item) {
            $(value).append(new Option(item, item));
        });
    });

    // Load the new configurator state when the value is changed
    $('.value').live('change', function() {
        $(this).after('<div class="throbber filter" />');
        // Read the current id and fetch a new one that is higher
        old_id = parseInt($(this).attr('name').replace('value', ''));
        id = old_id + 1;
        // If we have a valid value and few enough ids, insert a field
        if($(this).val()) {
            // jQuery will only serialize enabled objects, so enable,
            // serialize then disable. Also stab yourself and perhaps find a
            // better way to solve this without hacking on the library
            $('[id^=type]').attr('disabled', null);
            $('[id^=value]').attr('disabled', null);
            fields = $('#configurator').formSerialize();
            $('[id^=type]').attr('disabled', 'disabled');
            $('[id^=value]').attr('disabled', 'disabled');
            $.ajax({
                data: fields,
                dataType: 'json',
                url: '/railroad/configurator/formstate',
                success: function(data, textStatus, XMLHttpRequest) {
                    $('#configurator').data('state', data);
                    if(data['options'].length) {
                        // Clone the two boxes, change their id/names and
                        // empty the new clones. Not perfectly clean but
                        // preferable to inserting raw html, and allows us to
                        // easily copy all properties of the original html
                        // template.
                        $('#type0').clone()
                                   .attr('id', 'type' + id)
                                   .attr('name', 'type' + id)
                                   .empty()
                                   .append(new Option())
                                   .attr('disabled', null)
                                   .appendTo('#options');

                        // Have to add a space between them
                        $('#options').append(' ');

                        $('#value0').clone()
                                    .attr('id', 'value' + id)
                                    .attr('name', 'value' + id)
                                    .empty()
                                    .attr('disabled', null)
                                    .appendTo('#options');
                       
                        // And a return after them
                        $('#options').append('<br />');

                        $.each(data['options'], function(index, item) {
                            $('#type' + id).append(new Option(item, item));
                        });
                        if(data['ready']) {
                            $('#submit').attr('disabled', null);
                        }
                    }
                    $('#configurator').find('.throbber').remove();
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    $('#configurator').find('.throbber').remove();
                }
            });
        }
    });

    // Automatically update any graphs which are set to ajax load
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

    // Start the AJAX graph refreshes
    setTimeout(autoFetchData, 60 * 1000);

});


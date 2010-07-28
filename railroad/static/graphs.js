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
function createGraph(element, path, callback) {
    $(element).append('<div class="throbber"></div>');
    $(element).remove('.empty');
    $.ajax({
        url: '/railroad/parserrd/' + path,
        dataType: 'json',
        success: function(data) {
            $(element).html("");
            data = formatGraph(element, data);
            $.plot($(element), data.data, data.options);
            if(data.options.yaxis.label) {
                $(element).before('<div class="ylabel">' +
                                  data.options.yaxis.label +
                                  '</div>');
            }
            if(data.empty == true) {
                $(element).append('<div class="empty">no data</div>');
            }
            if(callback != null) {
                callback();
            }
            $(element).remove('.throbber');
        },
        error: function(request, status, error) {
            // If there's an error just bail out
            $(element).html('');
            $(element).append('<div class="empty">error</div>');
        }
    });
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
        button = $(this)
        graph = button.closest('.graph_container')
                      .find('.graph');
        time = new Date();
        end = parseInt(time.getTime() / 1000);

        // Depending on which button is hit, change the behavior
        // TODO: Look at possibilities at cleaning this up

        if(button.hasClass('zoom')) {
            return;
        }

        button.closest('.graph_container')
              .find('.zoom')
              .hide();

        if(button.hasClass('reset')) {
            graph.addClass('ajax');
            update = graph.closest('.graph_container')
                          .find('.update');
            updateTimestamp(update);
            update.show();
        } if(button.hasClass('day') || button.hasClass('reset')) {
            start = parseInt(end - 60 * 60 * 24);
        } else if(button.hasClass('week')) {
            start = parseInt(end - 60 * 60 * 24 * 7);
        } else if(button.hasClass('month')) {
            start = parseInt(end - 60 * 60 * 24 * 30);
        } else if(button.hasClass('year')) {
            start = parseInt(end - 60 * 60 * 24 * 365);
        }

        graph.removeClass('ajax');

        serviceData = $(graph).data();

        path = [serviceData.host,
                serviceData.service,
                start,
                end,
                serviceData.res].join('/');

        createGraph(graph,
                    path,
                    function() {
                        button.closest('.graph_container')
                              .find('.options .selected')
                              .removeClass('selected');
                        button.addClass('selected');
                    });      
       
    });

    // Loop over the things to be graphed and produce graphs for each
    $(".graph").each(function(index, element) {

        // Store the graph data for usage later
        path = $(element).html();
        splitPath = path.split('/');
        $(element).data('host', splitPath[0]);
        $(element).data('service', splitPath[1]);
        $(element).data('res', splitPath[4]);

        createGraph(element, path);

        // Allow for zooming
        $(element).bind('plotselected', function (event, ranges) {
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
                            zoom = $(element).closest('.graph_container')
                                             .find('.zoom');
                            selected = $(element).closest('.graph_container')
                                                 .find('.selected');
                            selected.removeClass('selected');
                            zoom.show();
                            zoom.addClass('selected');
                        });
            
        });

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

            createGraph(element,
                        path,
                        function() {
                            updateTimestamp($(element)
                                            .closest('.graph_container')
                                            .find('.update'));
                            $(element).closest('.graph_container')
                                      .find('.update')
                                      .show();
                        });
        });
        setTimeout(autoFetchData, 60 * 1000);
    }
    setTimeout(autoFetchData, 1 * 1000);
});


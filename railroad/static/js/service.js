$(document).ready(function () {
    var json = $('#json_services').text();
    if (json) {
        var fields = $.parseJSON(json);
        getServiceObjsServicePage(fields);
    }
});
function getServiceObjsServicePage(ajaxData) {
    $.ajax({
        data: ajaxData,
        url: '/railroad/configurator/service_meta',
        type: 'POST',
        async: true,
        dataType: 'json',
        success: function (meta, textStatus, XMLHttpRequest) {
            $('#graphs').data('meta', meta);
            selectServiceObjsServicePage();

        },
        error: function () {
            console.log('failed to add graph html');
        }
    });
}

function selectServiceObjsServicePage() {

    var meta = $('#graphs').data('meta');

    $('#graphs').html('');
    for (var i=0; i<meta.length; i++) {
        if (meta[i].jQueryElement) {
            $(meta[i].jQueryElement).appendTo('#graphs');
        } else {
            meta[i].jQueryElement= $(meta[i].html);
            $(meta[i].jQueryElement).appendTo('#graphs');
        }
    }
    update_number_graphs();
    drawSOServicePage();
}
function drawSOServicePage() {
    var meta = $('#graphs').data('meta');
    var servicesToGraph = [];
    for (var i=0; i<meta.length; i++) {
        if (!meta[i].data || ! meta[i].isGraphed) {
            var host = meta[i].host;
            var service = meta[i].service;
            var start = meta[i].start;
            var uniq = meta[i].uniq;
            var end = meta[i].end;
            var serviceDict = {
                'host': host,
                'service': service,
                'start': start,
                'end': end,
                'uniq': uniq,
            };
            servicesToGraph.push(serviceDict);
        }
    }
    if (servicesToGraph.length > 0) {
        ajaxData = JSON.stringify(servicesToGraph);
        $.ajax({
            url: '/railroad/graphs',
            data: 'graphs=' + ajaxData,
            type: 'POST',
            async: true,
            dataType: 'json',
            success: function (data, textStatus, XMLHttpRequest) {
                var meta = $('#graphs').data('meta');
                for (var i=0; i < data.length; i++) {
                    var elem;
                    for (var j=0; j < meta.length; j++) {
                        if (data[i].slug === meta[j].slug && data[i].uniq === meta[j].uniq) {
                            meta[j].data = data[i];
                            if (meta[j].jQueryElement) {
                                elem = meta[j].jQueryElement.find('.graphInfo');
                            }
                        }
                    }
                    if (data[i].data && elem) {
                        drawServiceGraph(elem, data[i]);
                    } else {
                        $(elem).data('host', data[i].host);
                        $(elem).data('service', data[i].service);
                    }
                    if (data[i].uniq) {
                        elem = $('.{0}#{1}'.format(data[i].slug, data[i].uniq));
                    } else {
                        elem = $('.{0}'.format(data[i].slug));
                    }
                    for (var j=0; j < meta.length; j++) {
                        if (data[i].uniq) {
                            if (meta[j].slug === data[i].slug && meta[j].uniq === data[i].uniq ) {
                                meta[j].isGraphed = true;
                            }
                        } else {
                            if (meta[j].slug === data[i].slug) {
                                meta[j].isGraphed = true;
                            }
                        }
                    }
                }
            },
            error: function (request, textStatus, errorThrown) {
                console.log('There was an error in obtaining the data for graphs');
                console.log(request);
                console.log(errorThrown);
            }
        });
    }
}

// Plots the data in the given element
function drawServiceGraph (elemGraph, data) {
    drawGraph(elemGraph, data);

    var prevItem = null;
    $('.graph').parent().bind('plothover', function(event, pos, item) {
        if (item) {
            if(item != prevItem) {
                prevItem = item;
                var label = '<h3>{0} - {2}</h3><p>({1})</p>'.format(
                    item.series.label, new Date(pos.x).toString(),
                    numberFormatter(pos.y));

                showTooltip(item.pageX, item.pageY, label);
            }
        } else {
            $('#tooltip').remove();
        }
    });
}

$(document).ready(function() {
    /***** Make the downtime graph *****/
    if ($('#downtimegraph').length == 0) {
        // There is no downtime to schedule
        return;
    }
    var downtime = JSON.parse($('#downtimegraph').text());
    $('#downtimegraph').text('');

    var flot_data = []
    var yaxis_bits = [];
    var min_date = downtime[0].start_time;
    var max_date = downtime[0].end_time;

    for (var i=1; i<downtime.length; i++) {
        var dt = downtime[i];
        if (dt.start_time < min_date) {
            min_date = dt.start_time;
        }
        if (dt.end_time > max_date) {
            max_date = dt.end_time;
        }
    }

    min_date = new Date(min_date * 1000);
    max_date = new Date(max_date * 1000);

    console.log(max_date);

    for (var i=0; i<downtime.length; i++) {
        var dt = downtime[i];
        var y = downtime.length - i;
        var expr = dt.expr;
        if (expr.length > 30) {
            expr = expr.substring(0,30) + '...';
        }

        var startDate = new Date(dt.start_time * 1000);
        var endDate = new Date(dt.end_time * 1000);
        if (startDate < new Date()) {
            var offset = (max_date - new Date()) * 0.01;
            startDate = new Date().add({milliseconds: -offset});
        }

        flot_data.push({
            'label': expr,
            'data': [[ startDate, y, endDate, dt.key, ]],
        });
        yaxis_bits.push([y, expr]);
    }

    var flot_options = {
        series: {
            gantt: {
                active: true,
                show: true,
                barHeight: .5,
            },
        },
        xaxis: {
            min: new Date(),
            max: max_date,
            mode: "time",
        },
        yaxis: {
            min: 0.5,
            max: yaxis_bits.length+0.5,
            ticks: yaxis_bits,
        },
        grid: {
            hoverable: true,
            clickable: true,
        },
        legend: {
            show: false,
        },
    }

    var plot = $.plot($('#downtimegraph'), flot_data, flot_options);

    // fade out the left side of the graph.
    var ctx = plot.getCanvas().getContext('2d');
    var o = plot.pointOffset({ x: new Date(), y: 0.5 });
    console.log(o);
    var bounds = {
        left: o.left,
        bottom: o.top,
        top: o.top - plot.height(),
        right: o.left + plot.width(),
    };
    var gradient = ctx.createLinearGradient(bounds.left - 5, bounds.top,
                                            bounds.left + 2, bounds.top);
    gradient.addColorStop(0, 'rgba(255,255,255,1.0)');
    gradient.addColorStop(1, 'rgba(255,255,255,0.0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(bounds.left - 8, bounds.top, 10, plot.height());

    // Set up colored swatches next to the downtime text.
    var data = plot.getData();
    for (var i=0; i<data.length; i++) {
        var color = data[i].color;
        var expr = data[i].data[0][3];

        $('<div class="swatch" id="swatch{0}"></div>'.format(expr))
            .prependTo($('#{0} h3'.format(expr)))
            .css({
                "background-color": color,
                "border": "1px solid " + $.color.parse(color).scale('rgb', 0.7).toString(),
            })
    }

    // Highlight the text when hovering over the graph
    $('#downtimegraph').bind('plothover', function(event, pos, item) {
        if(item) {
            var key = item.datapoint[3];
            $('#' + key).addClass('hover');
        } else {
            $('.downtime').removeClass('hover');
        }
    });

    /***** Downtime cancellation *****/
    $('.canceldowntime').bind('click', function() {
        var button = this;
        var code = $(button).text();
        var expr;
        for (var i=0; i<downtime.length; i++) {
            if (downtime[i].key == code) {
                expr = downtime[i].expr;
                break;
            }
        }
        var conf = confirm('Cancel downtime "{0}" with code "{1}"?'.format(expr, code));
        if (conf) {
            $(this).after('<img src="/railroad-static/images/loading.gif" ' +
                'id="downtimeLoading" />');
            var data = {
                'command': 'cancelDowntime',
                'args': JSON.stringify([code]),
            }
            $.ajax({
                url: '/railroad/ajax/xmlrpc',
                data: data,
                dataType: 'text',
                success: function(count) {
                    if (count > 0) {
                        $(button).parents('.downtime').remove();
                    }
                    $('#downtimeLoading').remove();
                },
                error: function () {
                    $('#downtimeLoading').after(
                        '<span id="downtimeError" class="error">There was an error.</span>');
                    $('#downtimeLoading').remove();
                    setTimeout(function() {
                        $('#downtimeError').fadeOut(function() {
                            $('#downtimeError').remove()
                        });
                    }, 5000);
                }
            });
        }
    });
});

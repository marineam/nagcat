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

    for (var i=0; i<downtime.length; i++) {
        var dt = downtime[i]
        var y = downtime.length - i;
        var expr = dt.expr;
        if (expr.length > 30) {
            expr = expr.substring(0,30) + '...';
        }
        flot_data.push({
            'label': expr,
            'data': [[
                new Date(dt.start_time * 1000),
                y,
                new Date(dt.end_time * 1000),
                expr,
            ]],
        });
        yaxis_bits.push([y, expr]);
        if (dt.start_time < min_date) {
            min_date = dt.start_time;
        }
        if (dt.end_time > max_date) {
            max_date = dt.end_time;
        }
    }
    min_date = new Date(min_date * 1000);
    max_date = new Date(max_date * 1000);

    var flot_options = {
        series: {
            gantt: {
                active: true,
                show: true,
                barHeight: .5,
            },
        },
        xaxis: {
            min: min_date,
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
            markings: [{
                color: "#FF0000",
                lineWidth: 2,
                xaxis: {
                    from: new Date(),
                    to: new Date(),
                },
            }],
        },
        legend: {
            show: false,
        },
    }

    var plot = $.plot($('#downtimegraph'), flot_data, flot_options);

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

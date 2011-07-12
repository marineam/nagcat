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

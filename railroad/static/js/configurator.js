$(document).ready(function() {
    update_number_graphs();

    if ($('#permalink')) {
        var text = $('#permalink').val();
        text = window.location.protocol + window.location.host + text;
        $('#permalink').val(text);
    }
    // Bind the graph time range selection buttons
    $('.options .currentTime').live('click', function() {
        var dateRangeButton = this;

        if ($('#sync').prop('checked')) {
            var from = $('input[name=from]');
            var to = $('input[name=to]');
        } else {
            var dates = $(dateRangeButton).parents('.options')
                .siblings('.daterange');
            var from = $(dates).children('[name=from]');
            var to = $(dates).children('[name=to]');
        }

        var toDate = new Date();
        var fromDate = new Date();

        var timezoneString;
        if ($('#utc').prop('checked')) {
            var offset = new Date().getTimezoneOffset();
            toDate = toDate.setTimezoneOffset(0);
            fromDate = fromDate.setTimezoneOffset(0);
            timezoneString = "+0000";
        } else {
            timezoneString = getTimezoneString(fromDate);
        }

        if ($(dateRangeButton).attr('name') == 'day') {
            fromDate.setDate(fromDate.getDate()-1);
        } else if ($(dateRangeButton).attr('name') == 'week') {
            fromDate.setDate(fromDate.getDate()-7);
        } else if ($(dateRangeButton).attr('name') == 'month') {
            fromDate.setMonth(fromDate.getMonth()-1);
        } else if ($(dateRangeButton).attr('name') == 'year') {
            fromDate.setFullYear(fromDate.getFullYear()-1);
        }

        var dateFormat = 'MM/dd/yyyy HH:mm ';
        from.val(fromDate.toString(dateFormat) + timezoneString)
        to.val(toDate.toString(dateFormat) + timezoneString)

        updateZoom(from.first().parent().siblings('.graph').parent(),
            fromDate, toDate);
    });

    $('#localtime, #utc').bind('change', function() {
        // Guarantee that localstorage gets the change before redrawing graphs
        $('#configurator').trigger('change');
        graphs = $('.graph');
        graphs.each(function(index, element) {
            if ($(element).data('data')) {
                redrawGraph(element, $(element).data('data'));
            }
        });
    });

    // Autocomplete anything with class = "... autocomplete ..."
    $('.autocomplete').each(function () {
        $(this).autocomplete ( { source : "/railroad/ajax/autocomplete/" +
            $(this).attr('name'), minLength: 1, autoFocus: true,
                delay: 30,})
    });

    //Make it so pressing enter triggers the add graphs button
    $('#host,#service,#group').live('keypress', function(e) {
        if (e.keyCode === 13) {
            $('#add').trigger('click');
        }
    });


    $('#cleargraphs').click(function () {
        $('#graphs').data('meta', []);
        selectServiceObjs();
    });

    $('.graphcheckbox').change(function () {
        var checkp = true;
        var checkboxes = $('.service_row').filter('visible')
            .find('.graphcheckbox');
        checkboxes.each(function (index, element) {
            if (  ! $(element).prop('checked') ) {
                checkp = false;
            }
        });
        $('.checkall').prop('checked', checkp);
    });

    $('#clearform').bind('click', function () {
        $('#host').val("");
        $('#group').val("");
        $('#service').val("");
    });

    // Downtime requests
    $('#downtime-from, #downtime-to').val('');
    $('#downtime-comment').val('');

    makeDatetimePicker($('#downtime-from').first());
    makeDatetimePicker($('#downtime-to').last());

    var makeDowntimeError = function(err) {
        $('#downtime-submit')
            .after('<span id="downtimeError" class="error">{0}</span>'
                .format(err));

        setTimeout(function() {
            $('#downtimeError').fadeOut(function() {
                $('#downtimeError').remove();
            });
        }, 5000);
        console.log(err);
    }

    $('#configurator #downtime-submit').bind('click', function() {
        $('#downtime-submit').parent().after(
            '<img src="/railroad-static/images/loading.gif" ' +
            'id="downtimeLoading" />');
        $('.cancelcode').remove();

        // gather data
        var expr = '';
        var checkedServiceRows =
            $('.service_row').filter(
            function(index) {
                return $(this).find('.controls input')
                    .filter(':checked').length > 0;
            });

        if ($('#downtime-host').prop('checked')) {
            var hosts = [];
            $(checkedServiceRows).find('dd[name=host]')
                .each(function(index, element) {
                    hosts.push('host:' + $(element).text().trim());
                });
            hosts = hosts.uniqueList();
            expr = hosts.join(' or ')
        } else if ($('#downtime-service').prop('checked')) {
            var hosts = [];
            var services = [];
            var objs = [];
            $(checkedServiceRows).find('dd[name=host]')
                .each(function(index, element) {
                    hosts.push('host:"' + $(element).text().trim() + '"');
                });
            $(checkedServiceRows).find('dd[name=service]')
                .each(function(index, element) {
                    services.push('service:"' + $(element).text().trim() + '"');
                });
            for (var i=0; i<hosts.length; i++) {
                objs.push(hosts[i] + ' and ' + services[i]);
            }
            objs = objs.uniqueList();
            expr = '(' + (objs.join(') or (')) + ')';
        } else { 
            makeDowntimeError('Please choose to downtime by host or service');
            $('#downtimeLoading').remove();
            return;
        }

        if (!expr) {
            makeDowntimeError("No graphs selected.");
            $('#downtimeLoading').remove();
            return;
        }

        var from = $('#downtime-from').datepicker('getDate');
        var to = $('#downtime-to').datepicker('getDate');

        if (!(from && to)) {
            makeDowntimeError("Invalid dates!");
            $('#downtimeLoading').remove();
            return;
        }

        // Correct for time zones, since the datetimepicker doesn't store the
        // time zone. *glare*
        if ($('#utc').prop('checked')) {
            from.setTimezoneOffset(0);
            to.setTimezoneOffset(0);
        }
        from = Math.round(from.getTime() / 1000.0);
        to = Math.round(to.getTime() / 1000.0);

        var comment = $('#downtime-comment').prop('value');
        var user = $('#remoteuserid').text().trim();

        var args = [expr, from, to, user, comment]
        var data = {
            'command': 'scheduleDowntime',
            'args': JSON.stringify(args),
        }

        $.ajax({
            url: '/railroad/ajax/xmlrpc',
            data: data,
            dataType: 'text',
            success: function(cancellationCode) {
                console.log(cancellationCode);
                $('#downtimeLoading').after(('<span class="cancelcode">' +
                    'Success! Cancellation code: {0}</span>')
                    .format(cancellationCode));
                $('#downtimeLoading').remove();
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.log(textStatus + ': ' + jqXHR.responseText);
                makeDowntimeError(jqXHR.responseText);
                $('#downtimeLoading').remove();
            }
        });
    });

    /**** Tool bar ****/
    bindMenu($('#checkall'), $('#selectall.menu'));
    $('#selectall.menu li').bind('click', function(e) {
        switch ($(this).attr('name')) {
            case 'all':
                $('.service_row .controls input[type=checkbox]')
                    .prop('checked', true);
                break;
            case 'none':
                $('.service_row .controls input[type=checkbox]')
                    .prop('checked', false);
                break;
            case 'state_ok':
            case 'state_warning':
            case 'state_critical':
            case 'state_unknown':
                var button = this;
                $('.service_row').filter(':visible')
                .each(function(index, elem) {
                    var className = $(button).attr('name');
                    if ($(elem).children('.status_text').hasClass(className)) {
                        $(elem).children('.controls').children('input')
                            .prop('checked', true);
                    }
                });
                break;
        }
        $('.graphcheckbox').trigger('change');
        $('#selectall.menu').hide();
    });

    $('#remove_checked').bind('click', function() {
        var toRemove = [];
        var count = 0;
        $('.service_row').each(function(index, element) {
            if ($(element).find('.graphcheckbox').prop('checked')) {
                console.log($(element));
                toRemove.push($(element).find('.graphInfo'));
            }
        });
        if (toRemove.length > 0) {
            var meta = $('#graphs').data('meta');
            meta.removeMatching(function(e) {
                for (var i=0; i<toRemove.length; i++) {
                    if (toRemove[i].hasClass(e['slug'])) {
                        return true;
                    }
                }
                return false;
            });
            selectServiceObjs();
        }
        $('#checkall input').prop('checked', false);
    });
    $('#expand_checked').bind('click', function() {
        allChecked(expand_row);
    });
    $('#collapse_checked').bind('click', function() {
        allChecked(collapse_row);
    });

    bindMenu($('#sortby'), $('#sortbymenu'));
    $('#sortbymenu li').bind('click', function(e) {
        var name = $(this).attr('name');
        sortGraphs(name, !!$('#sortdirection').data('ascending'));

        $('#sortbymenu').hide();
        $('#sortby').data('lastSort', name);
    });
    $('#sortdirection').bind('click', function(e) {
        var name = $('#sortby').data('lastSort');
        if (!name) {
            name = 'host';
        }

        var ascend = !$(this).data('ascending');
        $(this).data('ascending', ascend);
        $(this).children('div').toggleClass('arrow_s_line')
                               .toggleClass('arrow_n_line');

        sortGraphs(name, ascend);
    });

    $('#check_controls input[type=checkbox]').bind('click', function(event) {
        $('.service_row .controls input[type=checkbox]').prop('checked',
            $(this).prop('checked'));
        // Don't trigger the click event of the parent
        event.stopPropagation();
    });

    $('#filter').bind('click', function () {
        lowValue = parseIntWithBase($('#min').val());
        // Since formatGraph bumps the max value by 20%, we need to reflect that
        // here as well, so the user 
        highValue = parseIntWithBase($('#max').val()) * 1.2;
        prepareFilterGraphs(lowValue, highValue);
    });

    $('#unfilter').bind('click', function () {
        selectServiceObjs();
    });

    // Handle configurator form submissions
    $('#configurator #add').bind('click', function() {
        $('#toolbar').after(
            '<img src="/railroad-static/images/loading.gif" ' +
            'id="graphsLoading" />');

        var fields = $('#configurator').serialize();
        $('#clearform').trigger('click');
        getServiceObjs(fields);
        return false;
    });

    // *************************** Row manipulations ***************************
    // Expand all/of type buttons
    $('#expansion_by_type').find('input').bind('change', function() {
        //To shorten the else if line below to < 80 chars
        var allCheckboxes = $(this).parent().siblings().children('input');
        if (! $(this).prop('checked')) {
            $('#expandall').prop('checked', false);
        } else if ($(allCheckboxes).not(':checked').length == 0) {
            // If all inputs are checked
            $('#expandall').prop('checked', true);
        }
    });

    $('#expandall').change(function() {
        var state = $(this).prop('checked');
        $('#expansion_by_type input').prop('checked', state);
    });

    /********** Page manipulations **********/
    // Note that page numbers are 0 based.
    $('#nextpage').bind('click', function() {
        var start = $('#graphs').data('start');
        var totalgraphs;
        if ( $('#graphs').data('meta') ) {
            totalgraphs = $('#graphs').data('meta').length;
        } else {
            console.log ('There was an error determining how many' +
                ' total graphs there are');
            return;
        }
        var perpage = getPerPage();
        var enabled = !!$(this).data('enabled');
        if (enabled && start <= totalgraphs - perpage) {
            start += perpage;
            $('#graphs').data('start', start);
            selectServiceObjs();
        }
    });
    $('#prevpage').bind('click', function() {
        var start = $('#graphs').data('start');
        var enabled = !!$(this).data('enabled');
        var perpage = getPerPage();
        if (enabled && start > 0) {
            start -= perpage;
            $('#graphs').data('start', start);
            selectServiceObjs();
        }
    });

    /********** Load preloaded graphs onto the page **********/
    var json = $('#json_services').text();
    json = unescape(json).trim();
    if (json) {
        var meta = $.parseJSON(json);
        $('#graphs').data('meta', meta);
        selectServiceObjs();
    }

    // Start the AJAX graph refreshes
    setTimeout(autoFetchData, 60 * 1000);

    // Permalink setup
    $('#closePermalinkDescription').click(function () {
        $('#permalinkDiv').hide();
    });

    $('#generateLink').click(function () {
        if (!$('#generateLink').data('description')) {
            $('#generateLink').text('Done');
            $('#permalinkDiv').show();
            $('#permalinkDiv').position({
                my: 'right top',
                at: 'left top',
                of: $('#generateLink')});

            $('#generateLink').data('description', true);
        } else {
            $('#permalinkDiv').hide();
            $('#generateLink').html(
                '<img src="/railroad-static/images/loading.gif" ' +
                'id="permalinkLoading" />');
            servicesList = generateState();
            $.ajax({
                data: {"services" :servicesList,
                    description: $('#permalinkDescription').val()},
                url: '/railroad/permalink/generate/',
                type: 'POST',
                success: function (link, textStatus, XMLHttpRequest) {
                        var text = window.location.protocol + "//" +
                            window.location.host +"/railroad/permalink/" + link;
                        $('#generateLink').before('<label>Permalink:</label>' +
                            '<input id="permalink" type="text"/>');
                        $('#permalink').val(text).select();
                        $('#permalink').attr('readonly', true);
                        $('#generateLink').remove();
                        $('#permalinkLoading').remove();
                    },
                error: function (error, textStatus, XMLHttpRequest) {
                        console.log("there was an error");
                        $('#generateLink').html('Get Permalink');
                        $('#generateLink')
                            .before('<span class="error">Error</span>');
                        setTimeout(function() {
                            $('#generateLink').siblings('.error').fadeOut(1000,
                                function() { $(this).remove(); });
                        }, 3000);
                        $('#generateLink').data('description', '');
                    },
            });
        }
    });
});

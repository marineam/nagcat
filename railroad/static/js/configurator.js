$(document).ready(function() {
    update_number_graphs();

    // Autocomplete anything with class = "... autocomplete ..."
    $('.autocomplete').each(function () {
        $(this).autocomplete ( { source : "/railroad/ajax/autocomplete/" +
            $(this).attr('name'), minLength: 1, autoFocus: true})
    });

    //Make it so pressing enter triggers the add graphs button
    $('#host,#service,#group').live('keypress', function(e) {
        if (e.keyCode === 13) {
            $('#add').trigger('click');
        }
    });

    $('#service_count').click(function () {
        $('.service_row').show();
        console.log(update_hidden_count);
        update_hidden_count();
        $(this).siblings().css({'opacity': 1.0}).data('checkp', false);
    });
    $('#stats .state_count').bind('click', function() {
        var buttonClass = $(this).attr('name');
        var checkp = !$(this).data('checkp');
        $(this).data('checkp', checkp);

        $('.service_row').each(function(index, element) {
            if ($(element).children('.status_text').hasClass(buttonClass)) {
                if (checkp) {
                    $(element).hide();
                } else {
                    $(element).show();
                }
            }
        });
        update_hidden_count();
    });

    $('#cleargraphs').click(function () {
        $('#graphs').data('meta', []);
        selectServiceObjs();
    });

    $('.graphcheckbox').change(function () {
        var checkp = true;
        var checkboxes = $('.graphcheckbox');
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
    $('#configurator .datetimerow input').datetimepicker();
    $('#configurator #downtime-submit').bind('click', function() {
        // gather data
        var expr = '';
        if ($('#downtime-host').prop('checked')) {
            var hosts = [];
            $('.service_row dd[name=host]').each(function(index, element) {
                hosts.push('host:' + $(element).text().trim());
            });
            hosts = hosts.uniqueList();
            expr = hosts.join(' or ')
        } else {
            var hosts = [];
            var services = [];
            var objs = [];
            $('.service_row dd[name=host]').each(function(index, element) {
                hosts.push('host:"' + $(element).text().trim() + '"');
            });
            $('.service_row dd[name=service]').each(function(index, element) {
                services.push('service:"' + $(element).text().trim() + '"');
            });
            for (var i=0; i<hosts.length; i++) {
                objs.push(hosts[i] + ' and ' + services[i]);
            }
            objs = objs.uniqueList();
            expr = objs.join(' or ')
        }

        if (!expr) {
            console.log('no graphs')
            return;
        }

        var from = $('#downtime-from').datepicker('getDate');
        var to = $('#downtime-to').datepicker('getDate');
        if (!(from && to)) {
            console.log('invalid dates');
            return;
        }
        from = Math.round(from.getTime() / 1000.0);
        to = Math.round(to.getTime() / 1000.0);

        var comment = $('#downtime-comment').prop('value');
        if (!expr) {
            console.log('no comment');
            return;
        }

        var user = $('#remoteuserid').text().trim();

        var args = [expr, from, to, user, comment]
        var data = {
            'url': 'http://localhost:8080',
            'command': 'scheduleDowntime',
            'args': JSON.stringify(args),
        }

        $('#downtime-submit').parent().after(
            '<img src="/railroad-static/images/loading.gif" ' +
            'id="downtimeLoading" />');

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
            error: function () {
                console.log('error');
                $('#downtimeLoading').after(
                    '<span class="error">There was an error.</span>');
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
                $('.service_row').each(function(index, elem) {
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
        allChecked(function(elem) {$(elem).remove();});
        update_number_graphs();
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


    // Handle configurator form submissions
    $('#configurator #add').bind('click', function() {
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
        var page = $('#graphs').data('curpage');
        var totalpages;
        if ($('#graphs').data('totalpages')) {
            totalpages = $('#graphs').data('totalpages');
        } else {
            totalpages = 1;
        }
        var enabled = !$(this).data('enabled');
        if (enabled && page < totalpages) {
            page += 1;
            $('#graphs').data('curpage', page);
            selectServiceObjs();
        }
    });
    $('#prevpage').bind('click', function() {
        var page = $('#graphs').data('curpage');
        var enabled = !$(this).data('enabled');
        if (enabled && page > 0) {
            page -= 1;
            $('#graphs').data('curpage', page);
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
});

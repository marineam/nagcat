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

// Execute setup code when page loads
$(document).ready(function() {
    /******* AJAX Helpers ******/
    $('body').ajaxStart(function() {
        if ($('#cursor').length == 0) {
            $('body').append('<images id="cursor" src="/railroad-static/' +
                'images/loading.gif" style="position: absolute;"/>');
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
        ajaxcall.push(getGraphDataByDiv(element));
    });
    ajaxcall = JSON.stringify(ajaxcall);
    $.ajax({
        dataType: 'json',
        url: '/railroad/graphs',
        data: {'graphs': ajaxcall},
        type: 'POST',
        success: function (data, textStatus, XMLHttpRequest) {
            for (var i=0; i < data.length; i++) {
                var element;
                if (data[i]['uniq']) {
                    element = $('.{0}#{1}'.format(data[i]['slug'],
                                                  data[i]['uniq']));
                } else {
                    element = $('.{0}'.format(data[i]['slug']));
                }
                drawGraph(element, data[i]);
            }

            $('#stats #graph_count').html('{0} graphs'.format(
                $('.graph').length));
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
    /* Anything in #configurator with a class of "... persist ..."
     * will get persistence.
     */
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
        $(this).autocomplete ( { source : "/railroad/ajax/autocomplete/" +
            $(this).attr('name' ), minLength : 1, autoFocus: true})
    });

    $('#cleargraphs').click(function () {
        $('.service_row').remove();
    });

    $('#clearform').bind('click', function () {
        $('#host').val("");
        $('#group').val("");
        $('#service').val("");
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

    // *************************** Row manipulations ***************************
    // Expand all/of type buttons
    $('#expansion_by_type').find('input').bind('change', function() {
        auto_expansion();
        //To shorten the else if line below to < 80 chars
        var allCheckboxes = $(this).parent().siblings().children('input');
        if (! $(this).prop('checked')) {
            $('#expandall').prop('checked', false);
        } else if ($(allCheckBoxes).not(':checked').length == 0) {
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
        if (! hints_hidden[$(this).attr('id')] &&
            ! hints_hidden["hide_all_hints"]) {
            $(this).css('display', 'block');
        }
    });

    /******** Sorting *********/
    $('#sortby').bind('change', sortGraphs);
    $('#reverse_sort').bind('change', sortGraphs);

    /****** Tool bar stuff *****/
    $('#check_controls input[type=checkbox]').bind('click', function(event) {
        $('.service_row .controls input[type=checkbox]').prop('checked', $(this).prop('checked'));
        // Don't trigger the click event of the parent
        event.stopPropagation();
    });

    var allChecked = function(func) {
        $('.service_row').each(function(index, elem) {
            if ($(elem).children('.controls').children('input').prop('checked')) {
                func(elem);
            }
        });
        $('.service_row .controls input[type=checkbox]').prop('checked', false);
        $('#checkall input').prop('checked', false);
    }
    $('#checkall').bind('click', function() {
        $('#selectall.menu').toggle();
    });
    $('#remove_checked').bind('click', function() {
        allChecked(function(elem) {$(elem).remove();});
    });
    $('#expand_checked').bind('click', function() {
        allChecked(expand_row);
    });
    $('#collapse_checked').bind('click', function() {
        allChecked(collapse_row);
    });

    $('#selectall.menu li').bind('click', function(e) {
        switch ($(this).attr('name')) {
            case 'all':
                $('.service_row .controls input[type=checkbox]').prop('checked', true);
                break;
            case 'none':
                $('.service_row .controls input[type=checkbox]').prop('checked', false);
                break;
            case 'state_ok':
            case 'state_warning':
            case 'state_critical':
            case 'state_unknown':
                var button = this;
                $('.service_row').each(function(index, elem) {
                    if ($(elem).children('.status_text').hasClass($(button).attr('name'))) {
                        $(elem).children('.controls').children('input').prop('checked', true);
                    }
                });
                break;
        }
        $('#selectall.menu').hide();
    });

    /******** Quicklook view ********/
    $('#quicklook .status_text, .host').bind('click', function() {
        $(this).siblings('ul').toggle();
    });
    $('#quicklook .status_text.state_ok').siblings('ul').hide();
    $('#quicklook .host').siblings('ul').hide();

});

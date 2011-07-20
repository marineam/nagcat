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

function saveFormPersistence(elemPersist) {
    var store = {};
    var value = null;
    $(elemPersist).find('.persist').each(function(index, element) {
        if ($(element).is('input')) {
            if ($(element).attr('type') === 'checkbox') {
                value = $(element).prop('checked');
            } else if ($(element).attr('type') === 'radio') {
                value = $(element).prop('checked');
            } else if ($(element).attr('type') === 'field') {
                value = $(element).val();
            }
        } else if ($(element).is('select')) {
            value = $(element).val();
        }

        if (value != null) {
            store[$(element).attr('id')] = value;
        }
    });
    var dictName = $(elemPersist).attr('id')
    localStorageSet(dictName, store)
    updateDebug();
}

function restoreFormPersistence(elemPersist) {
    var form_store = localStorageGet($(elemPersist).attr('id'));
    for (key in form_store) {
        element = $(elemPersist).find('#' + key);
        if ($(element).is('input')) {
            if ($(element).attr('type') === 'checkbox') {
                $(element).prop('checked', form_store[key]);
            } else if ($(element).attr('type') === 'radio') {
                $(element).prop('checked', form_store[key]);
            } else if ($(element).attr('type') === 'field') {
                $(element).val(form_store[key]);
            }
        } else if ($(element).is('select')) {
            $(element).val(form_store[key]);
        }
    }
}

// Execute setup code when page loads
$(document).ready(function() {
    /******* AJAX Helpers ******/
    $('body').ajaxStart(function() {
        if ($('#loading').length == 0) {
            $('body').append('<images id="loading" src="/railroad-static/' +
                'images/loading.gif" style="position: absolute;"/>');
        }
    });

    $('body').ajaxStop(function() {
        $('#loading').remove();
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

        to.datetimepicker('setDate', new Date());
        from.datetimepicker('setDate', new Date());

        if ($(this).attr('name') == 'week') {
            from.datetimepicker('setDate', '-1w');
        } else if ($(this).attr('name') == 'month') {
            from.datetimepicker('setDate', '-1m');
        } else if ($(this).attr('name') == 'year') {
            from.datetimepicker('setDate', '-1y');
        }

        to.datetimepicker('refresh')
        from.datetimepicker('refresh')
        updateZoom(from,to);
    });

    // Initialize the data for any graphs already on the page
    update_number_graphs();
    fetchAndDrawGraphDataByDiv();

    /**** CONFIGURATOR SETUP ****/

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
    $('#configurator').bind('change', function () {
        saveFormPersistence($('#configurator'));
    });

    $('#preference_panel').bind('change', function () {
        saveFormPersistence($('#preference_panel'));
    });

    // Restore persisted objects
    restoreFormPersistence($('#configurator'));
    restoreFormPersistence($('#preference_panel'));

    // Autocomplete anything with class = "... autocomplete ..."
    $('.autocomplete').each(function () {
        $(this).autocomplete ( { source : "/railroad/ajax/autocomplete/" +
            $(this).attr('id'), minLength : 1, autoFocus: true})
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
        $('.service_row').remove();
        update_number_graphs()
        update_hidden_count();
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
        $('#clearform').trigger('click');
        addHTML(fields);
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
    $('.hint').each(function(index, element) {
        var hintText = $(element).text();
        $('<div class="sprite info"></div>').insertBefore(element)
        .mouseover(function(e) {
            // on hover
            showTooltip(e.pageX, e.pageY, hintText);
        })
        .mouseout(function(e) {
            // on unhover
            $('#tooltip').remove();
        });
        $(element).remove();
    });

    /****** Tool bar stuff *****/
    $('#check_controls input[type=checkbox]').bind('click', function(event) {
        $('.service_row .controls input[type=checkbox]').prop('checked',
            $(this).prop('checked'));
        // Don't trigger the click event of the parent
        event.stopPropagation();
    });

    var allChecked = function(func) {
        $('.service_row').each(function(index, elem) {
            if ($(elem).children('.controls').children('input')
                    .prop('checked')) {
                func(elem);
            }
        });
        $('.service_row .controls input[type=checkbox]').prop('checked', false);
        $('#checkall input').prop('checked', false);
    }

    var bindMenu = function(button, menu) {
        var pos = $(button).offset();
        var height = $(button).height();
        $(menu).position({my: 'left top', at: 'left bottom', of: $(button)}).hide();
        $(button).bind('click', function() {
            $(menu).toggle();
        });
    }

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
        sortGraphs(name);
        $('#sortbymenu').hide();
        $('#sortby').data('lastSort', name);
    });
    $('#sortreverse input').bind('change', function(e) {
        var name = $('#sortby').data('lastSort');
        sortGraphs(name, $(this).prop('checked'));
        $('#sortby').data('lastSort', name);
    });

    $('#preferences').bind('click', function() {
        $('#preference_panel').toggle();
    });
    $('#close_preferences').bind('click', function() {
        $('#preference_panel').toggle();
    });

    /******** Quicklook view ********/
    $('#quicklook .status_text, .host').bind('click', function() {
        $(this).siblings('ul').toggle();
    });
    $('#quicklook .status_text.state_ok').siblings('ul').hide();
    $('#quicklook .host').siblings('ul').hide();

});

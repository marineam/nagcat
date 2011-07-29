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
    /**** GRAPH SETUP ****/

    // Bind the graph time range selection buttons
    $('.options input[type=button]').live('click', function() {
        var dateRangeButton = this;

        if ($('#sync').prop('checked')) {
            var from = $('input[name=from]');
            var to = $('input[name=to]');
        } else {
            var dates = $(dateRangeButton).parent().siblings('.daterange');
            var from = $(dates).children('[name=from]');
            var to = $(dates).children('[name=to]');
        }

        var toDate = new Date();
        var fromDate = new Date();

        if ($(dateRangeButton).attr('name') == 'day') {
            fromDate.setDate(fromDate.getDate()-1);
        } else if ($(dateRangeButton).attr('name') == 'week') {
            fromDate.setDate(fromDate.getDate()-7);
        } else if ($(dateRangeButton).attr('name') == 'month') {
            fromDate.setMonth(fromDate.getMonth()-1);
        } else if ($(dateRangeButton).attr('name') == 'year') {
            fromDate.setFullYear(fromDate.getFullYear()-1);
        }

        var dateFormat = 'MM/dd/yyyy HH:mm';
        from.val(fromDate.toString(dateFormat))
        to.val(toDate.toString(dateFormat))

        updateZoom(from.first().parent().siblings('.graph'), fromDate, toDate);
    });

    /* Initialize the data for any graphs already on the page. */
    //fetchAndDrawGraphDataByDiv();

    /** Debug **/
    $('#debug_check').prop('checked', localStorageGet('debug'));
    updateDebug();

    $('#debug_check').change(function () {
        localStorageSet('debug', $('#debug_check').prop('checked'));
        updateDebug();
    });

    $('#debug a').live('click', function() {
        localStorageClear();
    });

    /*** Preferences persistance ***/
    $('#preference_panel').bind('change', function () {
        saveFormPersistence($('#preference_panel'));
    });
    restoreFormPersistence($('#preference_panel'));

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

    // Start the AJAX graph refreshes
    setTimeout(autoFetchData, 60 * 1000);

    /******* Hint System *******/
    var hint_timeout = null;
    $('.hint').each(function(index, element) {
        var hintText = $(element).text().trim().replace(/  +/, ' ');
        $('<div class="sprite info"></div>').insertBefore(element)
            .attr('title', hintText);
        $(element).remove();
    });

    // Permalink setup
    $('#generateLink').click(function () {
        $('#generateLink').before(
            '<img src="/railroad-static/images/loading.gif" ' +
            'id="permalinkLoading" />');
        servicesList = generateState();
        $.ajax({
            data: {"services" :servicesList },
            url: '/railroad/permalink/generate/',
            type: 'POST',
            success: function (link, textStatus, XMLHttpRequest) {
                    var text = window.location.protocol + "//" +
                        window.location.host + "/railroad/permalink/" + link;
                    $('#generateLink').before('<label>Permalink:</label>' +
                        '<input id="permalink" type="text"/>');
                    $('#permalink').val(text).select();
                    $('#generateLink').remove();
                    $('#permalinkLoading').remove();
                },
            error: function (error, textStatus, XMLHttpRequest) {
                    console.log("there was an error");
                    $('#permalinkLoading').remove();
                    $('#generateLink')
                        .before('<span class="error">Error</span>');
                    setTimeout(function() {
                        $('#generateLink').siblings('.error').fadeOut(1000,
                            function() { $(this).remove(); });
                    }, 3000);
                },
        });
    });
});

/*
 * Copyright 2011 ITA Software, Inc.
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

/* This file should be for function definitions only, there should be no side
 * effects from running this file. */

/********** Form Persistence **********/

/* Save the state of the given form into localstorage. */
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

/* Restore the state of the given form from localstorage. */
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

/* Bind a menu div to a button's on click event. */
var bindMenu = function(button, menu) {
    var pos = $(button).offset();
    var height = $(button).height();
    $(menu).position({my: 'left top', at: 'left bottom', of: $(button)}).hide();
    $(button).bind('click', function() {
        $(menu).toggle();
    });
}

/* Update the all graphs check box to match the service row checkboxes. */
function allChecked(func) {
    $('.service_row').each(function(index, elem) {
        if ($(elem).children('.controls').children('input').prop('checked')) {
            func(elem);
        }
    });
    $('.service_row .controls input[type=checkbox]').prop('checked', false);
    $('#checkall input').prop('checked', false);
}

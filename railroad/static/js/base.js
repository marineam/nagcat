$(document).ready(function() {
    /*** Preferences ***/
    $('#preferences').bind('click', function() {
        $('#preference_panel').toggle();
        if ($('#preference_panel').css('display') === "none") {
            setTimeout(redrawOnClosePreference, 500);
        }
    });

    $('#close_preferences').bind('click', function() {
        $('#preference_panel').toggle();
        setTimeout(redrawOnClosePreference, 500);
    });

    $('#preference_panel').bind('change', function () {
        saveFormPersistence($('#preference_panel'));
        $('#preference_panel').data('changed', true);
    });
    restoreFormPersistence($('#preference_panel'));

    if (localStorageGet('preference_panel')) {
        if (!localStorageGet('preference_panel')['graphsPerPage']) {
           $('#graphsPerPage').val(25);
           $('#graphsPerPage').trigger('change');
        }
    }

    /*** Twirlers ***/
    $('.twirler').prepend('<div class="sprite tri_e"></div>');
    $('.twirler .target').live('click', function() {
        var twirl = $(this).parent();
        $(twirl).children('ul').toggle();
        var e = $(twirl).children('.sprite.tri_e, .sprite.tri_s')
            .toggleClass('tri_e').toggleClass('tri_s');
    });

    /******* Hint System *******/
    var hint_timeout = null;
    $('.hint').each(function(index, element) {
        var hintText = $(element).text().trim().replace(/  +/, ' ');
        $('<div class="sprite info"></div>').insertBefore(element)
            .attr('title', hintText);
        $(element).remove();
    });

    /*** Water marks in text boxes ***/
    $('.watermark').bind('focus', function() {
        var input = this;
        $(input).data('watermark', $(input).val())
        $(input).val("");
        $(input).removeClass("watermark");
    });

    $('.watermark').bind('blur', function() {
        var input = this;
        if ($(input).val() == "") {
            $(input).val($(input).data('watermark'))
                .addClass("watermark");
        }
    });
});

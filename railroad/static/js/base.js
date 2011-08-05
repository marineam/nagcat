$(document).ready(function() {
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

    $('.twirler').prepend('<div class="sprite tri_e"></div>');
    $('.twirler .target').live('click', function() {
        var twirl = $(this).parent();
        $(twirl).children('ul').toggle();
        var e = $(twirl).children('.sprite.tri_e, .sprite.tri_s')
            .toggleClass('tri_e').toggleClass('tri_s');
    });

    if (localStorageGet('preference_panel')) {
        if (!localStorageGet('preference_panel')['graphsPerPage']) {
           $('#graphsPerPage').val(25);
           $('#graphsPerPage').trigger('change');
        } 
    }
});

$(document).ready(function() {
    $('#preferences').bind('click', function() {
        $('#preference_panel').toggle();
    });

    $('#close_preferences').bind('click', function() {
        $('#preference_panel').toggle();
    });

    $('.twirler').prepend('<div class="sprite tri_e"></div>');
    $('.twirler .target').live('click', function() {
        var twirl = $(this).parent();
        $(twirl).children('ul').toggle();
        var e = $(twirl).children('.sprite.tri_e, .sprite.tri_s')
            .toggleClass('tri_e').toggleClass('tri_s');
    });
});

$(function() {
    /******** Quicklook view ********/
    $('#quicklook .status_text, .host').bind('click', function() {
        $(this).siblings('ul').toggle();
    });
    $('#quicklook .status_text.state_ok').siblings('ul').hide();
    $('#quicklook .host').siblings('ul').hide();
});

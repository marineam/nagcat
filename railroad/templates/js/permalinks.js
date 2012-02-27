$(document).ready(function () {

    $('.delete_link a').click(function () {
        var row = $(this).parents('.permalink_row');
        var link = $(this).attr('name');
        console.log(link);
        $.ajax({
            url: '{% url railroad.permalink.views.delete_link %}' + link,
            dataType: 'text',
            success: function (html, statusText, XMLHttpRequest) {
                $(row).remove();
                console.log(html);
            },
            error: function (error, statusText, XMLHttpRequest) {
                console.log("There was an error deleting the link");
            }
        });
    });
});

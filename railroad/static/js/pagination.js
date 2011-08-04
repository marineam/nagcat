$(document).ready(function () {

    var serviceObjects = [];
    var numGraphsOnPage;
    if (localStorageGet('preference_panel')) {
        if (localStorageGet('preference_panel')['numGraphsOnPage']) {
            numGraphsOnPage = localStorageGet('preference_panel'['numGraphsOnPage']);
        }
    }
    elif (!localStorageGet('preference_panel')) {
        numGraphsOnPage = 25;
    }
});

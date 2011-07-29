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

    // Initialize preloaded JSON, if applicable
    // initializeSO(serviceObjects)
    // serviceObject.each ( serviceObjects.push(serviceObject))

    // Select preloaded JSON
    // selectHTML(serviceObjects, pageNum, numGraphsOnPage)

    // Graph preloaded JSON
    // graphSO(serviceObjects, pageNum, numGraphsOnPage)

    // Get new JSON from forms?
    // initializeSO(serviceObjects)
    // selectHTML(serviceObjects, pageNum, numGraphsOnPage)
    // graphSO(serviceObjects, pageNum, numGraphsOnPage)

});

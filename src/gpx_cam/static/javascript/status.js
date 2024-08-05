var source = new EventSource('/status/');

source.onmessage = function(event) {
    var data = JSON.parse(event.data);

    if (data.latitude && data.longitude) {
        var latLonElement = document.getElementById('latLon');
        if (latLonElement) {
            var latLonAltitude = 'Latitude: ' + data.latitude + ', Longitude: ' + data.longitude + ', Altitude: ' + data.altitude;
            latLonElement.innerHTML = latLonAltitude;
        }
    }

    var statusTextElement = document.getElementById('statusText');
    if (statusTextElement) {
        statusTextElement.innerHTML = data.status;
    }
};
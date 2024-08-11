setInterval(function() {
    fetch('/settings')
        .then(response => response.json())
        .then(data => {
            msg = data.data.mav_msg_global_position_int
            lat = msg.lat;
            lon = msg.lon;
            alt = msg.alt;

            if (lat && lon && alt) {
                var latLonElement = document.getElementById('latLon');
                if (latLonElement) {
                    var latLonAltitude = 'Latitude: ' + lat + ', Longitude: ' + lon + ', Altitude: ' + alt;
                    latLonElement.innerHTML = latLonAltitude;
                }
            }

            var statusTextElement = document.getElementById('statusText');
            exposure = data.data.cam_exposure;
            analog_gain = data.data.analog_gain;
            digital_gain = data.data.digital_gain;            
            
            if (statusTextElement) {
                statusTextElement.innerHTML = 'Exposure: ' + exposure + ', Analog Gain: ' + analog_gain + ', Digital Gain: ' + digital_gain;
            }


            var recordingTimeElement = document.getElementById('clock');
            if (recordingTimeElement) {
                time = data.data.rec_time;
                if (time){
                    recordingTimeElement.innerHTML = parseFloat(data.rec_time).toFixed(2);
                }
                else{
                    recordingTimeElement.innerHTML = '0.00';
                }
                
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
}, 1000);
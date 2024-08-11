function formatTime(seconds) {
    const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
    const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
}



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

            var recordingStatus = document.getElementById('recordingStatus');
            if (recordingStatus) {
                recordingFilename = data.data.record_filename;
                time = formatTime(data.data.rec_time);
                if (data.data.is_recording){
                    recordingStatus.innerHTML = `Recording Status: [ ${recordingFilename} ] - [ ${time} ]`;
                }
                else{
                    recordingStatus.innerHTML = 'Recording Status [ Not Recording ] - [ 00:00:00 ]';
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
}, 1000);
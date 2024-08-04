var isRecording = false;

function sendFilename(filename) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", '/filename', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.send('videoFile=' + encodeURIComponent(filename));
}

function mapDifferenceToRadius(distance) {
    return (20 * distance + 200);
}

// Crude way of setting the page state based on the sse json data sent at 1 FPS
var source = new EventSource('/status/');
const currentDepthCircle = document.getElementById('current-depth');
const idealDepthCircle = document.getElementById('ideal-depth');
const idealDepth = -1; // Example ideal depth
const idealRadius = mapDifferenceToRadius(0);
idealDepthCircle.setAttribute('r', idealRadius);

function updateGauge(currentDepth) {
    const depthDifference = (idealDepth - currentDepth);
    const currentRadius = mapDifferenceToRadius(depthDifference);
    currentDepthCircle.setAttribute('r', currentRadius);
}

source.onmessage = function(event) {
    var data = JSON.parse(event.data);
    if (data.latitude && data.longitude) {
    var latLonAltitude = 'Latitude: ' + data.latitude + ', Longitude: ' + data.longitude + ', Altitude: ' + data.altitude;
    document.getElementById('latLon').innerHTML = latLonAltitude;
    }
    // set the record button state based on the recording status
    isRecording = data.isRecording;
    document.getElementById('recordButton').textContent = isRecording ? 'Stop' : 'Start';
    // Update the background color based on the recording status
    recordButton.style.backgroundColor = isRecording ? 'red' : 'green';
    //filename
    // document.getElementById('videoFile').value = data.record_filename;

    // Status text
    document.getElementById('statusText').innerHTML = data.status;
    
    // Update the gauge
    updateGauge((data.altitude));

};


var statusSource = new EventSource('/status/');
statusSource.onmessage = function(event) {
    // console.log(event.data);
    document.getElementById('statusText').innerHTML = event.data;
};

document.getElementById('recordButton').addEventListener('click', function() {
    isRecording = !isRecording;
    this.textContent = isRecording ? 'Stop' : 'Start';
    this.style.backgroundColor = isRecording ? 'red' : 'green';

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/record', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.send('isRecording=' + encodeURIComponent(isRecording));
});

document.addEventListener('DOMContentLoaded', function() {
    const exposureSpinner = document.getElementById('exposureSpinner');
    const framerateSpinner = document.getElementById('framerateSpinner');

    exposureSpinner.addEventListener('change', function() {
    let exposureValue = parseInt(this.value, 10);
    if (isNaN(exposureValue)) return; // Exit if the value is not a number

    // Clamp the value to ensure it's within the desired range
    exposureValue = Math.max(100, Math.min(exposureValue, 20000));
    this.value = exposureValue; // Update the input with the clamped value
    fetch('/set-exposure', {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json',
        },
        body: JSON.stringify({ exposure: exposureValue }),
    })
    .then(response => {
        if (response.ok) {
        return response.json();
        }
        throw new Error('Network response was not ok.');
    })
    .then(data => {
        console.log('Success:', data);
    })
    .catch((error) => {
        console.error('Error:', error);
    });
    });

    framerateSpinner.addEventListener('change', function() {
    let framerateValue = parseInt(this.value, 10);
    if (isNaN(framerateValue)) return; // Exit if the value is not a number

    // Clamp the value to ensure it's within the desired range
    framerateValue = Math.max(1, Math.min(framerateValue, 30));
    this.value = framerateValue; // Update the input with the clamped value
    fetch('/set-framerate', {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json',
        },
        body: JSON.stringify({ framerate: framerateValue }),
    })
    .then(response => {
        if (response.ok) {
        return response.json();
        }
        throw new Error('Network response was not ok.');
    })
    .then(data => {
        console.log('Success:', data);
    })
    .catch((error) => {
        console.error('Error:', error);
    });
    });
});

class Center {
    constructor() {
        this.stream = document.getElementById("stream");
        this.canvas = document.getElementById("canvas");
        this.context = this.canvas.getContext('2d');
        this.fps = 0;
        this.frameTimes = [];
        this.maxFrameCount = 10;
    }

    render() {
    }
}

window.onload = function() {
    var ws
    const jmuxer = new JMuxer({
        node: 'stream',
        mode: 'video',
        flushingTime: 0,
        fps: document.getElementById('framerateSpinner').value,
        debug: false
    });

    const center = new Center();

    function startWebSocket() {
        const ip = document.getElementById('ip').value;
        const port = document.getElementById('port').value;
        ws = new WebSocket([`ws://${ip}:${port}/ws/`]);
        ws.binaryType = 'arraybuffer';

        ws.addEventListener('message', function(event) {
            if (!document.hidden) {
                jmuxer.feed({
                    video: new Uint8Array(event.data)
                });

                center.render();
            }
        });



        ws.addEventListener('close', function() {
            console.log('WebSocket closed, retrying...');
            setTimeout(startWebSocket, 1000);
        });
    }

    startWebSocket();

    window.onresize = function() {
        center.render();
    };
    window.one = function() {
        center.render();
    };

    // set record button state
    document.getElementById('recordButton').textContent = isRecording ? 'Stop' : 'Start';
    recordButton.style.backgroundColor = isRecording ? 'red' : 'green';

};

function openFileManager() {
    window.open("http://192.168.2.3:8085", "_blank");
}

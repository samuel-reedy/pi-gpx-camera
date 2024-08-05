function quarticEaseInOut(t) {
    if (t < 0.5) {
        return 8 * t * t * t * t;
    } else {
        return 1 - Math.pow(-2 * t + 2, 4) / 2;
    }
}

function mapDifferenceToRadius(distance, sensitivity, minRadius, maxRadius) {
    const scaledDistance = Math.max(Math.min((distance - maxDepthDifference) / (minDepthDifference - maxDepthDifference), 1), 0);
    const percentage = quarticEaseInOut(scaledDistance);
    console.log(scaledDistance);
    console.log(scaledDistance);
    return minRadius + (maxRadius - minRadius) * percentage;
}

function updateGauge(currentDepth, idealDepth, sensitivity, minRadius, maxRadius) {
    const depthDifference = (idealDepth - currentDepth);
    const currentRadius = mapDifferenceToRadius(depthDifference, sensitivity, minRadius, maxRadius);
    currentDepthCircle.setAttribute('r', currentRadius);
}

const currentDepthCircle = document.getElementById('current-depth');
const idealDepthCircle = document.getElementById('ideal-depth');

var idealDepth;
var sensitivity;
const minRadius = 50
const maxRadius = 200
var minDepthDifference = 3
var maxDepthDifference = -3

function fetchGaugeParameters() {
    fetch('/gauge')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                idealDepth = data.data.ideal_depth;
                sensitivity = data.data.sensitivity;
                const idealRadius = mapDifferenceToRadius(0, sensitivity, minRadius, maxRadius);
                idealDepthCircle.setAttribute('r', idealRadius);
            }
        })
        .catch(error => console.error('Error fetching gauge parameters:', error));
}

// Initial fetch
fetchGaugeParameters();

// Poll for updates every 30 seconds
setInterval(fetchGaugeParameters, 1000);

var source = new EventSource('/status/');

source.onmessage = function(event) {
    var data = JSON.parse(event.data);
    updateGauge(data.altitude, idealDepth, sensitivity, minRadius, maxRadius);
};
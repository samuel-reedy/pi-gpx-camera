function quarticEaseInOut(t) {
    if (t < 0.5) {
        return 8 * t * t * t * t;
    } else {
        return 1 - Math.pow(-2 * t + 2, 4) / 2;
    }
}

function mapDifferenceToRadius(distance, minRadius, maxRadius, maxDepthDifference) {
    const scaledDistance = Math.max(Math.min((distance + maxDepthDifference) / (maxDepthDifference + maxDepthDifference), 1), 0);
    const percentage = quarticEaseInOut(scaledDistance);
    return minRadius + (maxRadius - minRadius) * percentage;
}

function updateGauge(currentDepth, idealDepth, minRadius, maxRadius, maxDepthDifference) {
    const depthDifference = (idealDepth - currentDepth);
    const currentRadius = mapDifferenceToRadius(depthDifference, minRadius, maxRadius, maxDepthDifference);
    
    currentDepthCircle.setAttribute('r', currentRadius);

    const textElement = document.getElementById('current-depth-text');
    updateTextPosition(textElement, currentDepthCircle, currentDepth, 'right');
}

const currentDepthCircle = document.getElementById('current-depth');
const idealDepthCircle = document.getElementById('ideal-depth');

var idealDepth;
var minRadius;
var maxRadius;
var maxDepthDifference;

function updateTextPosition(textObj, circleObj, text, position = 'right') {
    textObj.textContent = text.toFixed(2) + " m";

    const circleRadius = parseFloat(circleObj.getAttribute('r'));
    const textWidth = textObj.offsetWidth;
    const newX = circleRadius + textWidth/2;
    const newTranslate = position === 'right' ? `translate(${newX + 5}px, 0)` : `translate(-${newX + 5}px, 0)`;
    
    textObj.style.transform = newTranslate;
}


function fetchGaugeParameters() {
    fetch('/settings')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                idealDepth = data.data.ideal_depth;
                minRadius = data.data.min_radius;
                maxRadius = data.data.max_radius;
                maxDepthDifference = data.data.max_depth_difference;
                const idealRadius = mapDifferenceToRadius(0, minRadius, maxRadius, maxDepthDifference);
                idealDepthCircle.setAttribute('r', idealRadius);
                const textElement = document.getElementById('ideal-depth-text');
                updateTextPosition(textElement, idealDepthCircle, idealDepth, 'left');
            }
        })
        .catch(error => console.error('Error fetching gauge parameters:', error));
}

// Initial fetch
fetchGaugeParameters();

setInterval(fetchGaugeParameters, 1000);

var source = new EventSource('/status/');

source.onmessage = function(event) {
    var data = JSON.parse(event.data);
    updateGauge(data.altitude, idealDepth, minRadius, maxRadius, maxDepthDifference);
};
function quarticEaseInOut(t) {
    if (t < 0.5) {
        return 8 * t * t * t * t;
    } else {
        return 1 - Math.pow(-2 * t + 2, 4) / 2;
    }
}


function setRadius(circle, percentage_radius){
    const gaugeContainer = document.getElementById('depth-gauge-container');
    
    const width = gaugeContainer.clientWidth;
    const height = gaugeContainer.clientHeight;
    const radius = Math.min(width, height) / 2 * (percentage_radius / 100);

    circle.setAttribute('r', radius);
}

function mapDifferenceToRadius(distance, minRadius, maxRadius, maxDepthDifference) {
    const scaledDistance = Math.max(Math.min((distance + maxDepthDifference) / (maxDepthDifference + maxDepthDifference), 1), 0);
    const percentage = quarticEaseInOut(scaledDistance);
    return minRadius + (maxRadius - minRadius) * percentage;
}

function updateGauge(currentDepth, idealDepth, minRadius, maxRadius, maxDepthDifference) {
    if (isNaN(currentDepth)) {
        console.log("The distance is NaN");
        return;
    }
    
    const depthDifference = (idealDepth - currentDepth);
    const currentRadius = mapDifferenceToRadius(depthDifference, minRadius, maxRadius, maxDepthDifference);
    
    setRadius(currentDepthCircle, currentRadius);

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
                setRadius(idealDepthCircle, idealRadius);

                const textElement = document.getElementById('ideal-depth-text');
                updateTextPosition(textElement, idealDepthCircle, idealDepth, 'left');
            }
        })
        .catch(error => console.error('Error fetching gauge parameters:', error));
}

function UpdateDynamicGauge() {
    fetch('/settings')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                parmeters = data.data
                idealDepth = parmeters.ideal_depth;
                minRadius = parmeters.min_radius;
                maxRadius = parmeters.max_radius;
                maxDepthDifference = parmeters.max_depth_difference;

                if (parmeters.use_dvl){
                    
                    currentDistance = parmeters.dvl_distance;
                }
                else{
                    currentDistance = parmeters.mav_msg_global_position_int.alt;
                }
                updateGauge(currentDistance, idealDepth, minRadius, maxRadius, maxDepthDifference);
            }
        })
        .catch(error => console.error('Error fetching gauge parameters:', error));
}

// Initial fetch
fetchGaugeParameters();
setInterval(fetchGaugeParameters, 1000);

UpdateDynamicGauge();
setInterval(UpdateDynamicGauge, 100);
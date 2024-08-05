
function mapDifferenceToRadius(distance) {
    return (20 * distance + 200);
}

function updateGauge(currentDepth) {
    const depthDifference = (idealDepth - currentDepth);
    const currentRadius = mapDifferenceToRadius(depthDifference);
    currentDepthCircle.setAttribute('r', currentRadius);
}

const currentDepthCircle = document.getElementById('current-depth');
const idealDepthCircle = document.getElementById('ideal-depth');
const idealDepth = -1;
const idealRadius = mapDifferenceToRadius(0);
idealDepthCircle.setAttribute('r', idealRadius);
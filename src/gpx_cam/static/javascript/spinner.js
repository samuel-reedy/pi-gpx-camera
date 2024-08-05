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
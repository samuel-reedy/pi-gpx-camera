document.addEventListener("DOMContentLoaded", function() {
    // Retrieve the last filename from the configuration
    const lastFilename = getLastFilenameFromConfig();

    // Set the value of the input element
    const videoFileInput = document.getElementById("videoFile");

    // Function to retrieve the last filename from the configuration
    function getLastFilenameFromConfig() {
        fetch('/settings')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                recordingFilename = data.data.record_filename;
                videoFileInput.value = recordingFilename;
            }
        })
        .catch(error => console.error('Error fetching settings parameters:', error));
    }

    // Save the filename when it changes
    videoFileInput.addEventListener('change', function() {
        localStorage.setItem('lastFilename', videoFileInput.value);
    });
});
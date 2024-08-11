var isRecording = false;


window.addEventListener('load', function() {
    fetch('/settings')
        .then(response => response.json())
        .then(data => {
            isRecording = data.data.is_recording;
            var recordButton = document.getElementById('recordButton');
            recordButton.textContent = isRecording ? 'Stop' : 'Start';
            recordButton.style.backgroundColor = isRecording ? 'red' : 'green';
        })
        .catch(error => {
            console.error('Error:', error);
        });
});



document.getElementById('recordButton').addEventListener('click', function() {
    fetch('/settings')
        .then(response => response.json())
        .then(data => {
            isRecording = !data.data.is_recording;
            this.textContent = isRecording ? 'Stop' : 'Start';
            this.style.backgroundColor = isRecording ? 'red' : 'green';

            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/record', true);
            xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
            xhr.send('isRecording=' + encodeURIComponent(isRecording));
        })
        .catch(error => {
            console.error('Error:', error);
        });
});
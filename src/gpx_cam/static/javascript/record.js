var isRecording = false;

document.getElementById('recordButton').addEventListener('click', function() {
    isRecording = !isRecording;
    this.textContent = isRecording ? 'Stop' : 'Start';
    this.style.backgroundColor = isRecording ? 'red' : 'green';

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/record', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.send('isRecording=' + encodeURIComponent(isRecording));
});
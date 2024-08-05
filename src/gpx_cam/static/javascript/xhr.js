function sendFilename(filename) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", '/filename', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.send('videoFile=' + encodeURIComponent(filename));
}

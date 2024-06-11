#!/usr/bin/python3

# Mostly copied from https://picamera.readthedocs.io/en/release-1.13/recipes2.html
# Run this script, then point a web browser at http:<this-ip-address>:8075

import io
import logging
import socketserver
from http import server
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
# import time

_PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="1920" height="1080" />
# <img src="stream.mjpg" width="4056" height="3040" />
</body>
</html>
"""

PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<img id="snapshot" src="stream.mjpg" width="1920" height="1080" />

<input type="button" id="save" value="Save to PNG"> 

<script type="text/javascript">
document.getElementById('snapshot').onclick = function () {
    const canvas = document.createElement('canvas');
    const img = document.getElementById('snapshot');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    const link = document.createElement('a');
    link.download = 'snapshot.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
};

</script>

</body>
</html>
"""

__PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.2/FileSaver.min.js"></script>
<script>
var url = '/stream.mjpg'; // URL of the MJPG stream
var i = 0; // Counter for the file names

fetch(url).then(response => {
    var reader = response.body.getReader();
    var decoder = new TextDecoder('utf-8');

    return reader.read().then(function processResult(result) {
        if (result.done) return;

        var chunk = result.value;
        var text = decoder.decode(chunk);

        // Split the MJPG stream into JPEG frames using the boundary string
        var frames = text.split('--FRAME');

        frames.forEach(frame => {
            // Each frame starts with some headers, followed by the JPEG data
            var jpegData = frame.split('\\r\\n\\r\\n')[1];

            if (jpegData) {
                // Convert the JPEG data to a Blob
                var blob = new Blob([jpegData], {type: 'image/jpeg'});

                // Save the Blob as a file
                saveAs(blob, 'frame' + i + '.jpg');
                i++;
            }
        });

        // Continue reading the stream
        return reader.read().then(processResult);
    });
});
</script>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="1920" height="1080" />
</body>
</html>
"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
full_resolution = picam2.sensor_resolution
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]

picam2.configure(picam2.create_video_configuration(main={"size": half_resolution}))
picam2.controls.ExposureTime = 20000
picam2.set_controls({"FrameRate": 10.0})
# # We should be able to set the lens position and see it reported back.
# picam2.set_controls({'LensPosition': 1.5, 'FrameRate': 3})
# time.sleep(0.5)
# lp = picam2.capture_metadata()['LensPosition']
# if lp < 1.45 or lp > 1.55:
#     print("ERROR: lens position", lp, "should be 1.5")
# print("Lens responding")
output = StreamingOutput()
picam2.start_recording(JpegEncoder(), FileOutput(output))

try:
    address = ('', 8075)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    picam2.stop_recording()

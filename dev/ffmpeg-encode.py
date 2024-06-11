import cv2
import numpy as np
from picamera2.outputs import FfmpegOutput
import time
# see https://github.com/raspberrypi/picamera2/blob/a89eb1dc39578fb764d792d83ba34095a9597f80/picamera2/outputs/ffmpegoutput.py#L9


output = FfmpegOutput('test.avi',)
output.start()
for i in range (20  ):
    # Create a random 100x100 numpy array
    arr = np.random.randint(0, 256, (1000, 1000, 3), dtype=np.uint8)

    # Define the JPEG quality
    quality = 95

    # Encode the numpy array to JPEG
    is_success, buffer = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    output.outputframe(buffer.tobytes())
    time.sleep(0.5)

    if is_success:
        print("Image encoding successful")
    else:
        print("Error during image encoding")

output.stop()
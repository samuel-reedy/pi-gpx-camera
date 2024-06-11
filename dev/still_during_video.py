#!/usr/bin/python3

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder


# Encode a VGA stream, and capture a higher resolution still image half way through.

picam2 = Picamera2()
full_resolution = picam2.sensor_resolution
# 0.8 resolution
o8_resolution = [int(dim * 0.8) for dim in picam2.sensor_resolution]
o6_resolution = [int(dim * 0.6) for dim in picam2.sensor_resolution]
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]
third_resolution = [dim // 3 for dim in picam2.sensor_resolution]
quarter_resolution = [dim // 3 for dim in picam2.sensor_resolution]
# main_stream = {"size": half_resolution}
main_stream = {"size": full_resolution}
lores_stream = {"size": (640, 480)}
lores_stream = {"size": (1280, 960)}
# lores_stream = {"size": (1920, 1080)}
# lores_stream = {"size": quarter_resolution}
print(f"{main_stream = }")
print(f"{lores_stream = }")
video_config = picam2.create_video_configuration(main_stream, lores_stream, encode="lores", buffer_count=1)
picam2.configure(video_config)

encoder = H264Encoder(10000000)

picam2.start_recording(encoder, 'test.h264')
time.sleep(2)
# Get your image as a numpy array (OpenCV, Pillow, etc. but here we just create a bunch of noise). Note: HWC ordering

import numpy as np

# It's better to capture the still in this thread, not in the one driving the camera.
for i in range(10):
    # print(f"Recording frame {i}")
    time.sleep(0.1)
    raw = np.random.randint(0, 255, (10,10, 3), dtype=np.uint8)
    request = picam2.capture_request()
    # filename = f"/home/pi/usb/rpi-test-{main_stream['size']}-{i}.jpg"
    filename = f"rpi-test-{main_stream['size']}-{i}.jpg"
    # request.mak("main", filename)
    raw = request.make_array("main")
    # im = picam2.capture_array()
    # a = request.make_image("main")

    # request.save("main", filename)
    request.release()
    print(f"Still image captured {filename} {raw.shape =}")

time.sleep(2)
picam2.stop_recording()

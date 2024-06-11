#!/usr/bin/python3

import socket
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

picam2 = Picamera2()

# config = picam2.create_still_configuration({"size": (2028, 1520)})
config = picam2.create_still_configuration()
picam2.configure(config)

picam2.start()

np_array = picam2.capture_array()
print(np_array.shape)
picam2.capture_file(f"demo-{np_array.shape}.jpg")
picam2.stop()
video_config = picam2.create_video_configuration({"size": (1920, 1080)})
print(video_config)
print()
picam2.configure(video_config)
encoder = H264Encoder(1000000)

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.connect(("10.42.0.1", 10001))
    stream = sock.makefile("wb")
    picam2.start_recording(encoder, FileOutput(stream))
    time.sleep(20)
    picam2.stop_recording()
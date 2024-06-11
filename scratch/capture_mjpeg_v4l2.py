#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder

picam2 = Picamera2()

full_resolution = picam2.sensor_resolution
# 0.8 resolution
o8_resolution = [int(dim * 0.8) for dim in picam2.sensor_resolution]
o6_resolution = [int(dim * 0.6) for dim in picam2.sensor_resolution]
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]
third_resolution = [dim // 3 for dim in picam2.sensor_resolution]
quarter_resolution = [dim // 3 for dim in picam2.sensor_resolution]


# video_config = picam2.create_video_configuration()
video_config = picam2.create_video_configuration(main={"size": half_resolution})
picam2.configure(video_config)

encoder = MJPEGEncoder(10000000)

picam2.start_recording(encoder, 'test.mjpeg')
time.sleep(10)
picam2.stop_recording()

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput, FfmpegOutput
import time

picam2 = Picamera2()

full_resolution = picam2.sensor_resolution
# 0.8 resolution
o8_resolution = [int(dim * 0.8) for dim in picam2.sensor_resolution]
o6_resolution = [int(dim * 0.6) for dim in picam2.sensor_resolution]
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]
third_resolution = [dim // 3 for dim in picam2.sensor_resolution]
quarter_resolution = [dim // 3 for dim in picam2.sensor_resolution]
# main_stream = {"size": half_resolution}
main_stream = {'format': 'RGB888', 'size': full_resolution}
lores_stream = {"size": (640, 480)}
lores_stream = {"size": (1280, 960)}
# lores_stream = {"size": (1920, 1080)}
# lores_stream = {"size": quarter_resolution}
print(f"{main_stream = }")
print(f"{lores_stream = }")
video_config = picam2.create_video_


video_config = picam2.create_video_configuration(main_stream)
picam2.configure(video_config)
encoder = H264Encoder(repeat=True, iperiod=15)
output1 = FfmpegOutput("-f mpegts udp://<ip-address>:12345")
output2 = FileOutput()
encoder.output = [output1, output2]
# Start streaming to the network.
picam2.start_encoder(encoder)
picam2.start()
time.sleep(5)
# Start recording to a file.
output2.fileoutput = "test.h264"
output2.start()
time.sleep(5)
output2.stop()
# The file is closed, b
"""
    Version:
--------


"""

import logging
import os

import tornado.web, tornado.ioloop, tornado.websocket  
import tornado.gen
from string import Template
import io, os
import socket
import shutil
try:
    # assert False
    from picamera2 import Picamera2, MappedArray
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import Output
    import prctl
    import cv2
    import simplejpeg  # simplejpeg is a simple package based on recent versions of libturbojpeg for fast JPEG encoding and decoding.
# from picamera2.outputs import FfmpegOutput
# from .ffmpegoutput import FfmpegOutput
except:
    logging.error("Error in Picamera2, disabling the camera")


from pymavlink import mavutil
import time
import json

from datetime import datetime
import queue
import threading
import time

import signal
import subprocess
import math

import argparse

import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# start configuration
class Config:
    wsURL = "ws://my_ip/ws/"
    CAM_TYPE = "hq-6mm-CS-pi"
    RUN_CAMERA = False
    isRecording = False
    rec_start_position = None
    record_filename = "transect-001"
    RESOLUTION = None  # set by params
    REC_FRAMERATE = None # set by params
    CAM_FRAMERATE = 20
    JPG_QUALITY = None # set by params
    PORT = None # set by params
    mav_msg_GLOBAL_POSITION_INT = None 
    mav_satellites_visible = 0
    # resolution = [0, 0]
    framerate_js = CAM_FRAMERATE
    cam_exposure = None

try:
    # assert False
    picam2 = Picamera2()
    Config.RUN_CAMERA = True
except:
    logging.error("Error in Picamera2, disabling the camera")
    Config.RUN_CAMERA = False


def set_exposure(exposure):
    if Config.RUN_CAMERA:
        # clip 100 to 20000
        exposure = max(100, min(exposure, 20000))
        Config.cam_exposure = exposure
        picam2.set_controls({'ExposureTime': Config.cam_exposure})
        logging.debug(f"Set new exposure: {Config.cam_exposure}")

def set_framerate(exposure):
    if Config.RUN_CAMERA:
        framerate = max(1, min(exposure, 30))
        Config.CAM_FRAMERATE = framerate
        picam2.set_controls({'FrameRate': Config.CAM_FRAMERATE})
        logging.debug(f"Set new framerate: {Config.CAM_FRAMERATE}")

def set_camera():
    if Config.RUN_CAMERA:

        resolution = [int(dim * Config.RESOLUTION) for dim in picam2.sensor_resolution]
        main_stream = {'format': 'BGR888', 'size': resolution}
        lores_stream = {"size": (640, 480)}
        # lores_stream = {"size": (1280, 960)}
        # lores_stream = {"size": (1920, 1080)}

        logging.info(f"{main_stream = }")
        logging.info(f"{lores_stream = }")

        video_config = picam2.create_video_configuration(main_stream, lores_stream, encode="lores", buffer_count=3)
        picam2.configure(video_config)
        picam2.start()
        # picam2.controls.ExposureTime = 20000
        # picam2.set_controls({"ExposureTime": 20000, "FrameRate": Config.CAM_FRAMERATE})
        picam2.set_controls({"AeExposureMode": 1, "FrameRate": Config.CAM_FRAMERATE})    # 1 = short https://libcamera.org/api-html/namespacelibcamera_1_1controls.html
        set_exposure(2000)
        set_framerate(Config.CAM_FRAMERATE)


        PRE_CALLBACK = False
        if PRE_CALLBACK:
            colour = (255, 0, 0)
            origin = (0, 30)
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 1
            thickness = 2

            def apply_timestamp(request):
                with MappedArray(request, "main") as m:
                    # Calculate the width and height of the text box
                    (text_width, text_height) = cv2.getTextSize(str(Config.mav_msg_GLOBAL_POSITION_INT), font, scale, thickness)[0]
                    # Draw a black rectangle under the text
                    cv2.rectangle(m.array, (0, 30 - text_height - 5), (text_width, 40), (0, 0, 0), -1)
                    cv2.putText(m.array, str(Config.mav_msg_GLOBAL_POSITION_INT), (0, 30), font, scale, colour, thickness)
                    # cv2.putText(m.array, 'RECORDING', (1700, 1050), font, scale, (255, 0, 0), 3)

                    # Add camera settings to the overlay
                    exposure_text = f"Exposure: {Config.cam_exposure}"
                    framerate_text = f"FPS: {Config.CAM_FRAMERATE}"
                    settings_text = f"{exposure_text}, {framerate_text}"
                    (settings_text_width, settings_text_height) = cv2.getTextSize(settings_text, font, scale, thickness)[0]
                    cv2.rectangle(m.array, (0, 0), (settings_text_width, settings_text_height + 10), (0, 0, 0), -1)
                    cv2.putText(m.array, settings_text, (0, settings_text_height + 5), font, scale, colour, thickness)

            picam2.post_callback = apply_timestamp



focusPeakingColor = '1.0, 0.0, 0.0, 1.0'
focusPeakingthreshold = 0.055

centerColor = '255, 0, 0, 1.0'
centerThickness = 2

gridColor = '255, 0, 0, 1.0'
gridThickness = 2

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

def getFile(filePath):
    file = open(filePath,'r')
    content = file.read()
    file.close()
    return content

def templatize(content, replacements):
    tmpl = Template(content)
    return tmpl.substitute(replacements)

# indexHtml = templatize(getFile('index.html'), {'ip':Config.serverIp, 'port':Config.PORT, 'fps':Config.framerate_js})

# gridHtml = templatize(getFile('grid.html'), {'ip':Config.serverIp, 'port':Config.PORT, 'fps':Config.framerate_js,'color':gridColor, 'thickness':gridThickness})
# # focusHtml = templatize(getFile('focus.html'), {'ip':Config.serverIp, 'port':Config.PORT, 'fps':Config.framerate_js, 'color':focusPeakingColor, 'threshold':focusPeakingthreshold})
# jmuxerJs = getFile('jmuxer.min.js')


if Config.RUN_CAMERA:

    class FfmpegOutput(Output):
        """
        The FfmpegOutput class allows an encoded video stream to be passed to FFmpeg for output.
        """

        def __init__(self, output_filename, audio=False, audio_device="default", audio_sync=-0.3,
                    audio_samplerate=48000, audio_codec="aac", audio_bitrate=128000, pts=None):
            super().__init__(pts=pts)
            self.ffmpeg = None
            self.output_filename = output_filename
            self.timeout = 1 if audio else None
            # A user can set this to get notifications of FFmpeg failures.
            self.error_callback = None
            # We don't understand timestamps, so an encoder may have to pace output to us.
            self.needs_pacing = True

        def start(self):
            general_options = ['-loglevel', 'warning',
                            '-y', '-f', 'mjpeg']  # -y means overwrite output without asking, -f mjpeg means force input to mjpeg
            # We have to get FFmpeg to timestamp the video frames as it gets them. This isn't
            # ideal because we're likely to pick up some jitter, but works passably, and I
            # don't have a better alternative right now.
            video_input = ['-use_wallclock_as_timestamps', '1',
                        '-thread_queue_size', '64',  # necessary to prevent warnings
                        '-i', '-']
            video_codec = ['-c:v', 'copy']
            command = ['ffmpeg'] + general_options + video_input + \
                video_codec + self.output_filename.split()
            # The preexec_fn is a slightly nasty way of ensuring FFmpeg gets stopped if we quit
            # without calling stop() (which is otherwise not guaranteed).
            self.ffmpeg = subprocess.Popen(command, stdin=subprocess.PIPE, preexec_fn=lambda: prctl.set_pdeathsig(signal.SIGKILL))
            super().start()

        def stop(self):
            super().stop()
            if self.ffmpeg is not None:
                self.ffmpeg.stdin.close()  # FFmpeg needs this to shut down tidily
                try:
                    # Give it a moment to flush out video frames, but after that make sure we terminate it.
                    self.ffmpeg.wait(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    # We'll always end up here when there was an audio strema. Ignore any further errors.
                    try:
                        self.ffmpeg.terminate()
                    except Exception:
                        pass
                self.ffmpeg = None

        def outputframe(self, frame, keyframe=True, timestamp=None):
            if self.recording and self.ffmpeg:
                # Handle the case where the FFmpeg prcoess has gone away for reasons of its own.
                try:
                    self.ffmpeg.stdin.write(frame)
                    self.ffmpeg.stdin.flush()  # forces every frame to get timestamped individually
                except Exception as e:  # presumably a BrokenPipeError? should we check explicitly?
                    self.ffmpeg = None
                    
                    if self.error_callback:
                        self.error_callback(e)
                    else:
                        logging.warning(f"Error in ffmpeg outputframe {e}")
                else:
                    self.outputtimestamp(timestamp)


    class StreamingOutput(Output):
        def __init__(self):
            # self.frameTypes = PiVideoFrameType()
            self.loop = None
            self.buffer = io.BytesIO()

        def setLoop(self, loop):
            self.loop = loop

        def outputframe(self, frame, keyframe=True, timestamp=None):            
            self.buffer.write(frame)
            if self.loop is not None and wsHandler.hasConnections():
                self.loop.add_callback(callback=wsHandler.broadcast, message=self.buffer.getvalue())
            self.buffer.seek(0)
            self.buffer.truncate()

class wsHandler(tornado.websocket.WebSocketHandler):
    connections = []

    def open(self):
        self.connections.append(self)

    def on_close(self):
        self.connections.remove(self)

    def on_message(self, message):
        pass

    @classmethod
    def hasConnections(cl):
        if len(cl.connections) == 0:
            return False
        return True

    @classmethod
    async def broadcast(cl, message):
        for connection in cl.connections:
            try:
                await connection.write_message(message, True)
            except tornado.websocket.WebSocketClosedError:
                pass
            except tornado.iostream.StreamClosedError:
                pass

    def check_origin(self, origin):
        return True



class indexHandler(tornado.web.RequestHandler):
    def get(self):
        server_host = self.request.host.split(':')[0]  # Split to remove port if present
        serverIp = socket.gethostbyname(server_host)  # Resolve host name to IP
        centerHtml = templatize(getFile('index.html'), {'ip':serverIp, 'port':Config.PORT, \
                                                        'fps':Config.framerate_js, 'record_filename':Config.record_filename, 'exposure': Config.cam_exposure, 'framerate': Config.CAM_FRAMERATE,\
                                                            'isRecording': 'true' if Config.isRecording else 'false'})
        self.write(centerHtml)


class gridHandler(tornado.web.RequestHandler):
    def get(self):
        server_host = self.request.host.split(':')[0]  # Split to remove port if present
        serverIp = socket.gethostbyname(server_host)  # Resolve host name to IP
        gridHtml = templatize(getFile('grid.html'), {'ip':serverIp, 'port':Config.PORT, 'fps':Config.framerate_js,'color':gridColor, 'thickness':gridThickness})
        self.write(gridHtml)

class focusHandler(tornado.web.RequestHandler):
    def get(self):
        server_host = self.request.host.split(':')[0]  # Split to remove port if present
        serverIp = socket.gethostbyname(server_host)  # Resolve host name to IP
        focusHtml = templatize(getFile('focus.html'), {'ip':serverIp, 'port':Config.PORT, 'fps':Config.framerate_js, 'color':focusPeakingColor, 'threshold':focusPeakingthreshold})
        self.write(focusHtml)

class jmuxerHandler(tornado.web.RequestHandler):
    def get(self):
        jmuxerJs = getFile('jmuxer.min.js')
        self.set_header('Content-Type', 'text/javascript')
        self.write(jmuxerJs)


def gps_to_meters_east_north(lat1, lon1, lat2, lon2):
    R = 6371e3  # Radius of the Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    lambda1 = math.radians(lon1)
    lambda2 = math.radians(lon2)

    delta_phi = phi2 - phi1
    delta_lambda = lambda2 - lambda1

    x = delta_lambda * math.cos((phi1 + phi2) / 2)  # East-west distance
    y = delta_phi  # North-south distance

    return R * x, R * y

class StatusHandler(tornado.web.RequestHandler):
    clients = set()
    status = ''

    def initialize(self):
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Connection', 'keep-alive')
        self.count = 0


    def _get_latlon(self):
        if Config.mav_msg_GLOBAL_POSITION_INT is not None:
            msg = Config.mav_msg_GLOBAL_POSITION_INT
            n_satellites = Config.mav_satellites_visible

            if Config.rec_start_position is not None:
                altitude = msg.alt / 1000.0
                start_lat, start_lon, start_alt = Config.rec_start_position
                east, north = gps_to_meters_east_north(start_lat, start_lon, msg.lat/1.0e7, msg.lon/1.0e7)
                data = {"latlon": f"East: {east:.1f}, North: {north:.1f}, altitude: {altitude}, Satellites: {n_satellites}"}                      
            else:
                altitude = msg.alt / 1000.0
                lat = msg.lat / 1.0e7
                lon = msg.lon / 1.0e7
                
                data = {
                    'altitude': altitude,
                    'latitude': lat,
                    'longitude': lon
                }
            return data
        return None
    
    def _get_record_state(self):
        return {"isRecording": Config.isRecording}
    def _get_status(self):
        return {"status": self.status}

    def _get_record_filename(self):
        return {"record_filename": Config.record_filename}
    
    async def get(self):
        while True:
            if self.request.connection.stream.closed():
                logging.info("Stream is closed")
                # break out of generator loop
                break

            data = self._get_latlon()
            if data is not None:
                data.update(self._get_record_state())
                data.update(self._get_record_filename())
                data.update(self._get_status())
                data = json.dumps(data)
                try:
                    self.write(f"data: {data} \n\n")
                    self.count += 1
                    await self.flush()  # Flush the data to the client
                except Exception as e:
                    logging.warning("Error in StatusHandler", e)
                    pass

            await tornado.gen.sleep(1)  # Wait for 1 second

    @classmethod
    def update_status(cls, status):
        cls.status = status

def move_file_to_complete(filename):
    data_folder = os.path.abspath("../../data")

    complete_folder = os.path.join(data_folder, "complete")
    recording_folder = os.path.join(data_folder, "recording")

    recording_path = os.path.join(recording_folder, f"{filename}.avi")
    complete_path = os.path.join(complete_folder, f"{filename}.avi")
    
    if not os.path.exists(complete_folder):
        os.makedirs(complete_folder)

    try:
        shutil.move(recording_path, complete_path)
        logging.info(f"File {filename}.avi moved to complete folder.")
    except FileNotFoundError:
        logging.error(f"File {filename}.avi not found in data folder.")
    except PermissionError as e:
        logging.error(f"Permission denied while moving file {filename}.avi: {e}")
    print(f"Recording path: {recording_path}")
    print(f"Complete path: {complete_path}")


class RecordHandler(tornado.web.RequestHandler):
    def post(self):

        is_recording = self.get_argument('isRecording') == 'true'
        if is_recording:

            # check for dir and create if needed 
            if not os.path.exists("../../data/recording/"):
                os.makedirs("../../data/recording/")
            
            Config.isRecording = True
            self.cap_que = queue.Queue(maxsize=2)
            self.jpg_que = queue.Queue(maxsize=2)

  
            def capture_arr():
                logging.info('Starting capture Thread')

                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 1
                thickness = 2
                colour = (0,255, 0)
                # Time delay for g_FRAMERATE frames per second
                delay = 1 / Config.REC_FRAMERATE
                logging.debug(f"{Config.REC_FRAMERATE = }")
                frame_count = 0
                while Config.isRecording:
                    start_time = time.time()
                    arr = picam2.capture_array()
                    text = f'#{frame_count}'
                    frame_count += 1
                    if Config.mav_msg_GLOBAL_POSITION_INT is not None:
                        msg = Config.mav_msg_GLOBAL_POSITION_INT
                        text += f', {msg.lat / 1.0e7}, {msg.lon/ 1.0e7}, {msg.alt / 1000.0}'

                    (text_width, text_height) = cv2.getTextSize(text, font, scale, thickness)[0]
                    # Draw a black rectangle under the text
                    cv2.rectangle(arr, (0, 30 - text_height-5), (text_width, 40), (0, 0, 0), -1)
                    cv2.putText(arr, str(text), (0, 30), font, scale, colour, thickness)

                    start = time.time()
                    buffer = simplejpeg.encode_jpeg(arr, quality=Config.JPG_QUALITY, colorspace='RGB', colorsubsampling='420', fastdct=True)
                    logging.debug(f"simple-jpeg encode time = {time.time() - start} {len(buffer) = }")

                    if self.jpg_que.full():
                        self.jpg_que.get() # If the queue is full, remove an item before adding a new one
                    self.jpg_que.put(buffer)
    
                    elapsed_time = time.time() - start_time
                    if elapsed_time < delay:
                        time.sleep(delay - elapsed_time)
      

            # Define your recording logic in a function
            def record(record_filename):
                fn_vid = f'../../data/recording/{record_filename}.avi' if Config.RUN_CAMERA else 'No Camera Found'

                logging.info(f"Recording started to {fn_vid}")

                logging.debug('Starting record Thread')
                status = f'Recording to {fn_vid}'

                StatusHandler.update_status(status)
                quality = 90
                if Config.RUN_CAMERA:
                    output = FfmpegOutput(fn_vid,)
                    output.start()
                fps = 0
                frame_count = 0
                start_time = time.time()
                last_time = start_time
                while Config.isRecording:
                    if Config.RUN_CAMERA:
                        try:
                            jpg = self.jpg_que.get(timeout=0.1)
                            output.outputframe(jpg)
                        except queue.Empty:
                            continue
                        except Exception as e:
                            logging.error(f"Error in record thread {e}")


                    else:
                        time.sleep(1)


                    frame_count += 1
                    avg_fps = frame_count / (time.time() - start_time)
                    # get the filesize of the video
                    try:
                        filesize = os.path.getsize(fn_vid) if Config.RUN_CAMERA else 0
                    except Exception as e:
                        filesize = 0

                    # on every second
                    if time.time() - last_time > 1: 

                        status = f'Video fps = {avg_fps:.2f}  {frame_count = }  {filesize = }'
                        StatusHandler.update_status(status)
                        last_time = time.time()

                # save video
                vid_status = fn_vid
                if Config.RUN_CAMERA:
                    output.stop()
                    vid_status = f'Video saved to {fn_vid}'

                status = f'{vid_status}'

                StatusHandler.update_status(status)

            def record_max_size():
                while Config.isRecording:
                    record()
                


            # Create and start a thread running the record function
            self.rec_thread = threading.Thread(target=record, args=(Config.record_filename,))
            self.rec_thread.daemon = True
            self.rec_thread.start()
            if Config.RUN_CAMERA:
                self.cap_thread = threading.Thread(target=capture_arr)
                self.cap_thread.daemon = True
                self.cap_thread.start()

        else:
            logging.info("Recording stopped")
            Config.isRecording = False
            Config.rec_start_position = None
            move_file_to_complete(Config.record_filename)
            # self.thread.join()

def move_file_to_complete(filename):
    data_folder = os.path.abspath("../../data")

    complete_folder = os.path.join(data_folder, "complete")
    recording_folder = os.path.join(data_folder, "recording")

    recording_path = os.path.join(recording_folder, f"{filename}.avi")
    complete_path = os.path.join(complete_folder, f"{filename}.avi")

    if not os.path.exists(complete_folder):
        os.makedirs(complete_folder)

    try:
        if os.path.exists(complete_path):
            i = 1
            while os.path.exists(os.path.join(complete_folder, f"{filename}({i}).avi")):
                i += 1
            complete_path = os.path.join(complete_folder, f"{filename}({i}).avi")
            logging.info(f"File {filename}.avi already exists in complete folder. Renaming to {filename}({i}).avi")
        shutil.move(recording_path, complete_path)
        logging.info(f"File {filename}.avi moved to complete folder.")
    except FileNotFoundError:
        logging.error(f"File {filename}.avi not found in data folder.")
    except PermissionError as e:
        logging.error(f"Permission denied while moving file {filename}.avi: {e}")




class FilenameHandler(tornado.web.RequestHandler):
    def post(self):
        Config.record_filename = self.get_argument('videoFile')
        logging.info(f"Set Record filename: {Config.record_filename }")


class ExposureHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            # Assuming the exposure value is sent as a JSON object {"exposure": value}
            exposure_data = json.loads(self.request.body)
            new_exposure = exposure_data.get('exposure')

            if new_exposure is not None:

                set_exposure(new_exposure)
                self.write({"status": "success", "message": "Exposure updated successfully."})
            else:
                self.set_status(400)  # Bad Request
                self.write({"status": "error", "message": "Invalid exposure value."})
        except Exception as e:
            logging.error(f"Error updating exposure: {e}")
            self.set_status(500)  # Internal Server Error
            self.write({"status": "error", "message": "Failed to update exposure."})
        self.finish()


class FramerateHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            # Assuming the framerate value is sent as a JSON object {"framerate": value}
            framerate_data = json.loads(self.request.body)
            new_framerate = framerate_data.get('framerate')

            if new_framerate is not None:

                set_framerate(new_framerate)
                self.write({"status": "success", "message": "Framerate updated successfully."})
            else:
                self.set_status(400)  # Bad Request
                self.write({"status": "error", "message": "Invalid framerate value."})
        except Exception as e:
            logging.error(f"Error updating framerate: {e}")
            self.set_status(500)  # Internal Server Error
            self.write({"status": "error", "message": "Failed to update framerate."})
        self.finish()

class old_StatusHandler(tornado.web.RequestHandler):
    clients = set()
    status = ''

    def initialize(self):
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Connection', 'keep-alive')
        self.count = 0

    def open(self):
        StatusHandler.clients.add(self)

    def on_close(self):
        StatusHandler.clients.remove(self)


    async def get(self):
        while True:
            if self.request.connection.stream.closed():
                logging.debug("Stream is closed")
                # break out of generator loop
                break
            try:
                self.write(f"data: {self.status} \n\n")
                await self.flush()
            except Exception as e:
                logging.error("Error in SSEHandler", e)
                pass
            await tornado.gen.sleep(1)  # Wait for 1 second

    @classmethod
    def update_status(cls, status):
        cls.status = status




import time
from pymavlink import mavutil
import sys 
import tty
import termios




# LensPosition = 10
LensPosition = 2
file_cnt = 0
FOCUS_INC = 0.5

def keyboard_handler(fd, events):

    # # This function will be called whenever there is input on stdin
    # message = sys.stdin.readline()
    # print(f"You typed: {message}")
    # This function will be called whenever a key is pressed
    key = os.read(fd, 1)

    if key == b'w':
        LensPosition += FOCUS_INC
        LensPosition = max(0, min(LensPosition, 10))
        focal_distance = 1/(LensPosition+0.00001)
        # picam2.set_controls({'LensPosition': LensPosition})
        # print(f"{focal_distance = }  {LensPosition = }")

    if key == b's':
        # clip focal_distance to 0 and 500  (5m)
        LensPosition -= FOCUS_INC
        LensPosition = max(0, min(LensPosition, 10))
        focal_distance = 1/(LensPosition+0.00001)
        # picam2.set_controls({'LensPosition': LensPosition})
        # print(f"{focal_distance = }  {LensPosition = }")
        StatusHandler.update_status(f'New file_cnt {file_cnt}')
        file_cnt += 1


    if key == b'q':
        # Stop the loop
        loop.stop()
        # picam2.stop()
        # print("********  Stop the loop")



def process_mavlink_data():

    # Start a connection listening to a UDP port
    the_connection = mavutil.mavlink_connection(f'udpin:0.0.0.0:{Config.MAVPORT}')
    # the_connection = mavutil.mavlink_connection('udpin:0.0.0.0:14445')
    # Wait for the first heartbeat 
    # This sets the system and component ID of remote system for the link
    logging.info("Waiting for heartbeat from system")
    the_connection.wait_heartbeat()
    logging.info("Heartbeat from system (system %u component %u)" % (the_connection.target_system, the_connection.target_system))

    # Wait for the vehicle to send GPS_RAW_INT message
    time.sleep(1)

    the_connection.mav.param_request_list_send(
        the_connection.target_system, the_connection.target_component
    )

    while True:
        time.sleep(0.01)
        try: 
            # Wait for a GPS_RAW_INT message with a timeout of 10 seconds
            msg = the_connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=10)
            Config.mav_msg_GLOBAL_POSITION_INT = msg


            msg = the_connection.recv_match(type='GPS_RAW_INT', blocking=True, timeout=10)
            Config.mav_satellites_visible = msg.satellites_visible

            if msg is not None:
                pass
            else:
                logging.info('No GPS_RAW_INT message received within the timeout period')
        except:
            logging.error('Error while waiting for GPS_RAW_INT message')

    


def update_status_periodically():

    while True:
        # Example: Update the status with a new value
        resolution = [int(dim * Config.RESOLUTION) for dim in picam2.sensor_resolution] if Config.RUN_CAMERA else [0, 0]
        StatusHandler.update_status(f'Resolution = {resolution}, record framerate = {Config.REC_FRAMERATE}, JPG Quality = {Config.JPG_QUALITY}')
        time.sleep(1)  # Update status every 1 seconds
        for i in range(10):
            md = picam2.capture_metadata()
            StatusHandler.update_status(f'ExposureTime:{md["ExposureTime"]}, AnalogueGain: {md["AnalogueGain"]}, DigitalGain: {md["DigitalGain"]}')
            time.sleep(1)  # Update status every 1 seconds

loop = None
KEYBOARD = False
def main():

    parser = argparse.ArgumentParser(description='Run the Rpi camera app.')
    parser.add_argument('--resolution', '-r', type=float, help='Resolution of the video: >0.2 <1.0', default=1.0)
    parser.add_argument('--framerate_record', '-fr', type=int, help='Framerate of the record', default=2)
    # parser.add_argument('--framerate_camera', '-fc', type=int, help='Framerate of the camera', default=10)
    parser.add_argument('--jpg_quality', '-q', type=int, help='Quality of the JPEG encoding', default=95)
    parser.add_argument('--port', '-p', type=int, help='html port', default=8075)
    parser.add_argument('--mavport', '-mp', type=int, help='mavlink port', default=14570)    

    args = parser.parse_args()
    # clip the resolution to 0.2 and 1.0
    args.resolution = max(0.2, min(args.resolution, 1.0))
    args.framerate_record = max(1, min(args.framerate_record, 5))
    # args.framerate_camera = max(1, min(args.framerate_camera, 30))
    args.jpg_quality = max(50, min(args.jpg_quality, 100))



    # Now you can access the values with args.resolution, args.framerate, and args.jpg_quality

    Config.RESOLUTION, Config.REC_FRAMERATE, Config.JPG_QUALITY, Config.PORT, Config.MAVPORT  \
        = args.resolution, args.framerate_record,  args.jpg_quality, args.port, args.mavport

    logging.info(f"{Config.RESOLUTION = }, {Config.REC_FRAMERATE = }, {Config.CAM_FRAMERATE = }, \
          {Config.JPG_QUALITY = }, {Config.PORT = }, {Config.MAVPORT = }")

    set_camera()
    

    # Create a new thread and start it
    mavlink_thread = threading.Thread(target=process_mavlink_data, daemon=True)
    mavlink_thread.start()

    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    
    # directory_to_serve = os.path.join(os.path.dirname(__file__), 'static')
    # directory_to_serve = os.path.dirname(__file__)
    # directory_to_serve = '/static'

    requestHandlers = [
        (r"/ws/", wsHandler),
        (r"/center", indexHandler),
        (r"/grid", gridHandler),
        (r"/focus", focusHandler),
        (r"/jmuxer.min.js", jmuxerHandler),
        (r"/record", RecordHandler), 
        (r"/filename", FilenameHandler),
        (r"/status/", StatusHandler),
        (r"/set-exposure", ExposureHandler),
        (r"/set-framerate", FramerateHandler), 
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static_dir}), 
        (r"/", indexHandler),    # this one is last so not to interfere with the above routes
    ]



    # Start the status update thread
    status_update_thread = threading.Thread(target=update_status_periodically)
    status_update_thread.daemon = True  # Daemonize thread
    status_update_thread.start()



    if KEYBOARD:
        # Save the current terminal settings
        old_settings = termios.tcgetattr(sys.stdin)

    try:
        if KEYBOARD:
            # Set the terminal to unbuffered mode
            tty.setcbreak(sys.stdin.fileno())

        if Config.RUN_CAMERA:
            output = StreamingOutput()
            encoder = H264Encoder(repeat=True, framerate=Config.CAM_FRAMERATE, qp=20, iperiod=Config.CAM_FRAMERATE)
            encoder.output = output
            picam2.start_recording(encoder, output)

        application = tornado.web.Application(requestHandlers)
        try:
            application.listen(Config.PORT)
        except Exception as e:
            logging.error(f"Error in application.listen(serverPort) {e}")
            logging.error("is the application running already? , in a service?")
            return
            
        loop = tornado.ioloop.IOLoop.current()

        if Config.RUN_CAMERA:
            output.setLoop(loop)
        if KEYBOARD:
            # Add the keyboard handler to the IOLoop
            loop.add_handler(sys.stdin.fileno(), keyboard_handler, loop.READ)

        loop.start()
    except KeyboardInterrupt:
        if Config.RUN_CAMERA:
            picam2.stop_recording()

        loop.stop()
        # print("********  KeyboardInterrupt")
    finally:
        if KEYBOARD:
            # print("********  Restore the terminal settings")
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()
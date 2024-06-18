"""
    Version:
--------


"""

import os

import tornado.web, tornado.ioloop, tornado.websocket  
import tornado.gen
from string import Template
import io, os, socket
# try:
from picamera2 import Picamera2, MappedArray
from picamera2.encoders import H264Encoder
from picamera2.outputs import Output
# from picamera2.outputs import FfmpegOutput
# from .ffmpegoutput import FfmpegOutput
# except:
#     print("Error in Picamera2, disabling the camera")
#     RUN_CAMERA = False

from pymavlink import mavutil
import time
import cv2
# import qoi
import simplejpeg  # simplejpeg is a simple package based on recent versions of libturbojpeg for fast JPEG encoding and decoding.

import gpxpy
import gpxpy.gpx

from datetime import datetime
import queue
import threading
import time

import signal
import subprocess

import prctl
import argparse

# rgb = np.random.randint(low=0, high=255, size=(224, 244, 3)).astype(np.uint8)

# Write it:
# _ = qoi.write("img.qoi", rgb)

# start configuration

wsURL = "ws://my_ip/ws/"

CAM_TYPE = "hq-6mm-CS-pi"
DO_RECORD = False
record_filename = "transect-001"
g_RESOLUTION, g_REC_FRAMERATE, g_CAM_FRAMERATE, g_JPG_QUALITY, g_PORT = 0.8, 2, 10, 95, 8075
GLOBAL_POSITION_INT_msg = None
resolution = [0, 0]
framerate_js = g_CAM_FRAMERATE
try:
    # assert False
    picam2 = Picamera2()
    RUN_CAMERA = True
except:
    print("Error in Picamera2, disabling the camera")
    RUN_CAMERA = False

def set_camera():
    if RUN_CAMERA:

        resolution = [int(dim * g_RESOLUTION) for dim in picam2.sensor_resolution]
        main_stream = {'format': 'BGR888', 'size': resolution}
        # lores_stream = {"size": (640, 480)}
        # lores_stream = {"size": (1280, 960)}
        lores_stream = {"size": (1920, 1080)}

        print(f"{main_stream = }")
        print(f"{lores_stream = }")

        video_config = picam2.create_video_configuration(main_stream, lores_stream, encode="lores", buffer_count=3)
        picam2.configure(video_config)
        picam2.start()
        # picam2.controls.ExposureTime = 20000
        picam2.set_controls({"ExposureTime": 20000, "FrameRate": g_CAM_FRAMERATE})

        colour = (0,255, 0)
        origin = (0, 30)
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1
        thickness = 2


        PRE_CALLBACK = False
        if PRE_CALLBACK:
            def apply_timestamp(request):
                global GLOBAL_POSITION_INT_msg
                # timestamp = time.strftime("%Y-%m-%d %X")
                with MappedArray(request, "main") as m:
                    # Calculate the width and height of the text box
                    (text_width, text_height) = cv2.getTextSize(str(GLOBAL_POSITION_INT_msg), font, scale, thickness)[0]
                    # Draw a black rectangle under the text
                    cv2.rectangle(m.array, (0, 30 - text_height-5), (text_width, 40), (0, 0, 0), -1)
                    cv2.putText(m.array, str(GLOBAL_POSITION_INT_msg), (0, 30), font, scale, colour, thickness)
                    # cv2.putText(m.array, 'RECORDING', (1700, 1050), font, scale, (255, 0, 0), 3)


            picam2.pre_callback = apply_timestamp


focusPeakingColor = '1.0, 0.0, 0.0, 1.0'
focusPeakingthreshold = 0.055

centerColor = '255, 0, 0, 1.0'
centerThickness = 2

gridColor = '255, 0, 0, 1.0'
gridThickness = 2
# end configuration

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('8.8.8.8', 0))  
serverIp = s.getsockname()[0]

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

indexHtml = templatize(getFile('index.html'), {'ip':serverIp, 'port':g_PORT, 'fps':framerate_js})

gridHtml = templatize(getFile('grid.html'), {'ip':serverIp, 'port':g_PORT, 'fps':framerate_js,'color':gridColor, 'thickness':gridThickness})
focusHtml = templatize(getFile('focus.html'), {'ip':serverIp, 'port':g_PORT, 'fps':framerate_js, 'color':focusPeakingColor, 'threshold':focusPeakingthreshold})
jmuxerJs = getFile('jmuxer.min.js')


class FfmpegOutput(Output):
    """
    The FfmpegOutput class allows an encoded video stream to be passed to FFmpeg for output.

    This means we can take advantange of FFmpeg's wide support for different output formats.

    """

    def __init__(self, output_filename, audio=False, audio_device="default", audio_sync=-0.3,
                 audio_samplerate=48000, audio_codec="aac", audio_bitrate=128000, pts=None):
        super().__init__(pts=pts)
        self.ffmpeg = None
        self.output_filename = output_filename
        # self.audio = audio
        # self.audio_device = audio_device
        # self.audio_sync = audio_sync
        # self.audio_samplerate = audio_samplerate
        # self.audio_codec = audio_codec
        # self.audio_bitrate = audio_bitrate
        # If we run an audio stream, FFmpeg won't stop so we'll give the video stream a
        # moment or two to flush stuff out, and then we'll have to terminate the process.
        self.timeout = 1 if audio else None
        # A user can set this to get notifications of FFmpeg failures.
        self.error_callback = None
        # We don't understand timestamps, so an encoder may have to pace output to us.
        self.needs_pacing = True

    def start(self):
        general_options = ['-loglevel', 'warning',
                           '-y', '-f', 'mjpeg']  # -y means overwrite output without asking
        # We have to get FFmpeg to timestamp the video frames as it gets them. This isn't
        # ideal because we're likely to pick up some jitter, but works passably, and I
        # don't have a better alternative right now.
        video_input = ['-use_wallclock_as_timestamps', '1',
                       '-thread_queue_size', '64',  # necessary to prevent warnings
                       '-i', '-']
        video_codec = ['-c:v', 'copy']
        # audio_input = []
        # audio_codec = []
        # if self.audio:
        #     audio_input = ['-itsoffset', str(self.audio_sync),
        #                    '-f', 'pulse',
        #                    '-sample_rate', str(self.audio_samplerate),
        #                    '-thread_queue_size', '1024',  # necessary to prevent warnings
        #                    '-i', self.audio_device]
        #     audio_codec = ['-b:a', str(self.audio_bitrate),
        #                    '-c:a', self.audio_codec]

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
        self.write(indexHtml)

class centerHandler(tornado.web.RequestHandler):
    

    def get(self):
        centerHtml = templatize(getFile('center.html'), {'ip':serverIp, 'port':g_PORT, 'fps':framerate_js, 'record_filename':record_filename, 'color':centerColor, 'thickness':centerThickness})
        self.write(centerHtml)

class gridHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(gridHtml)

class focusHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(focusHtml)

class jmuxerHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/javascript')
        self.write(jmuxerJs)


class SSEHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Connection', 'keep-alive')
        self.count = 0

    async def get(self):
        global GLOBAL_POSITION_INT_msg
        while True:
            if self.request.connection.stream.closed():
                print("Stream is closed")
                # break out of generator loop
                break
            try:
                if GLOBAL_POSITION_INT_msg is not None:
                    msg = GLOBAL_POSITION_INT_msg
                    altitude = msg.alt / 1000.0
                    lat = msg.lat/ 1.0e7
                    lon = msg.lon/ 1.0e7

                    self.write(f"data: {lat = }  {lon = }  {altitude = } \n\n")
                    self.count += 1
                    await self.flush()
            except Exception as e:
                print("Error in SSEHandler", e)
                pass
            await tornado.gen.sleep(1)  # Wait for 1 second

class RecordHandler(tornado.web.RequestHandler):
    def post(self):
        global DO_RECORD, GLOBAL_POSITION_INT_msg, record_filename, g_REC_FRAMERATE, g_JPG_QUALITY


        is_recording = self.get_argument('isRecording') == 'true'
        if is_recording:

            # check for dir and create if needed 
            if not os.path.exists("../../data"):
                os.makedirs("../../data")
            
            fn_gpx = f"../../data/{record_filename}.gpx" if GLOBAL_POSITION_INT_msg else 'No position MAV messages found'
            fn_vid = f'../../data/{record_filename}.avi' if RUN_CAMERA else 'No Camera Found'
            if GLOBAL_POSITION_INT_msg is not None:
                gpx = gpxpy.gpx.GPX()

                # Create a new track in our GPX file
                gpx_track = gpxpy.gpx.GPXTrack(name='transect 1', description='transect 1 description')
                gpx.tracks.append(gpx_track)

                # Create first segment in our GPX track:
                gpx_segment = gpxpy.gpx.GPXTrackSegment()
                gpx_track.segments.append(gpx_segment)



            DO_RECORD = True
            self.cap_que = queue.Queue(maxsize=2)
            self.jpg_que = queue.Queue(maxsize=2)

  
            def capture_arr():
                print('Starting capture Thread')

                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 1
                thickness = 2
                colour = (0,255, 0)
                # Time delay for g_FRAMERATE frames per second
                delay = 1 / g_REC_FRAMERATE
                frame_count = 0
                while DO_RECORD:
                    start_time = time.time()
                    arr = picam2.capture_array()
                    text = f'#{frame_count}'
                    frame_count += 1
                    if GLOBAL_POSITION_INT_msg is not None:
                        msg = GLOBAL_POSITION_INT_msg
                        text += f', {msg.lat / 1.0e7}, {msg.lon/ 1.0e7}, {msg.alt / 1000.0}'

                    (text_width, text_height) = cv2.getTextSize(text, font, scale, thickness)[0]
                    # Draw a black rectangle under the text
                    cv2.rectangle(arr, (0, 30 - text_height-5), (text_width, 40), (0, 0, 0), -1)
                    cv2.putText(arr, str(text), (0, 30), font, scale, colour, thickness)

                    start = time.time()
                    buffer = simplejpeg.encode_jpeg(arr, quality=g_JPG_QUALITY, colorspace='RGB', colorsubsampling='420', fastdct=True)
                    print(f"simple-jpeg encode time = {time.time() - start} {len(buffer) = }")

                    if self.jpg_que.full():
                        self.jpg_que.get() # If the queue is full, remove an item before adding a new one
                    self.jpg_que.put(buffer)
    
                    elapsed_time = time.time() - start_time
                    if elapsed_time < delay:
                        time.sleep(delay - elapsed_time)
      

            # Define your recording logic in a function
            def record():
                global record_filename
                print('Starting record Thread')
                status = f'Recording to {fn_gpx} & {fn_vid}'
                print(status)
                StatusHandler.update_status(status)
                quality = 90
                if RUN_CAMERA:
                    output = FfmpegOutput(fn_vid,)
                    output.start()
                fps = 0
                frame_count = 0
                start_time = time.time()
                last_time = start_time
                while DO_RECORD:
                    if GLOBAL_POSITION_INT_msg is not None:
                        msg = GLOBAL_POSITION_INT_msg
                        altitude = msg.alt / 1000.0
                        lat = msg.lat / 1.0e7
                        lon = msg.lon/ 1.0e7
                        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon, elevation=altitude, time=datetime.now(), speed=0.0,symbol='Waypoint'))
                        # todo add photo frame number

                    # print(f'{GLOBAL_POSITION_INT_msg = }')
                    if RUN_CAMERA:
                        try:
                            jpg = self.jpg_que.get(timeout=0.1)
                            output.outputframe(jpg)
                        except queue.Empty:
                            continue
                        except Exception as e:
                            print(f"Error in record thread {e}")


                    else:
                        time.sleep(1)


                    frame_count += 1
                    avg_fps = frame_count / (time.time() - start_time)

                    # on every second
                    if time.time() - last_time > 1: 
                        status = f'video fps = {avg_fps:.2f}  {frame_count = }'
                        print(status)
                        StatusHandler.update_status(status)
                        last_time = time.time()

                # save video and gpx
                vid_status = fn_vid
                gpx_status = fn_gpx
                if RUN_CAMERA:
                    output.stop()
                    vid_status = f'video saved to {fn_vid}'
                if GLOBAL_POSITION_INT_msg is not None:
                    with open(fn_gpx, 'w') as f:
                        f.write(gpx.to_xml())
                        gpx_status += f'gpx saved to {fn_gpx}'

                status = f'{gpx_status}, {vid_status}'
                print(status)
                StatusHandler.update_status(status)

            # Create and start a thread running the record function
            self.rec_thread = threading.Thread(target=record)
            self.rec_thread.daemon = True
            self.rec_thread.start()
            if RUN_CAMERA:
                self.cap_thread = threading.Thread(target=capture_arr)
                self.cap_thread.daemon = True
                self.cap_thread.start()





        else:
            print("Recording stopped")
            DO_RECORD = False
            # self.thread.join()



class FilenameHandler(tornado.web.RequestHandler):
    def post(self):
        global record_filename
        record_filename = self.get_argument('videoFile')
        print(f"Record filename: {record_filename }")


class StatusHandler(tornado.web.RequestHandler):
    clients = set()
    status = ''

    def initialize(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')
        self.set_header('connection', 'keep-alive')

    def open(self):
        StatusHandler.clients.add(self)

    def on_close(self):
        StatusHandler.clients.remove(self)


    async def get(self):
        while True:
            if self.request.connection.stream.closed():
                print("Stream is closed")
                # break out of generator loop
                break
            try:
                self.write(f"data: {self.status} \n\n")
                await self.flush()
            except Exception as e:
                print("Error in SSEHandler", e)
                pass
            await tornado.gen.sleep(1)  # Wait for 1 second

    @classmethod
    def update_status(cls, status):
        cls.status = status

# directory_to_serve = os.path.join(os.path.dirname(__file__), 'static')
# # directory_to_serve = os.path.dirname(__file__)
# directory_to_serve = '/static'

# requestHandlers = [
#     (r"/ws/", wsHandler),
#     (r"/", indexHandler),
#     (r"/center/", centerHandler),
#     (r"/grid/", gridHandler),
#     (r"/focus/", focusHandler),
#     (r"/jmuxer.min.js", jmuxerHandler),
#     (r"/sse/", SSEHandler),
#     (r"/record", RecordHandler), 
#     (r"/filename", FilenameHandler),
#     (r"/status/", StatusHandler),

# ]
# resolution = [int(dim * g_RESOLUTION) for dim in picam2.sensor_resolution]
# print(resolution)
# StatusHandler.update_status(f'Resolution = {resolution}, record framerate = {g_REC_FRAMERATE}, JPG Quality = {g_JPG_QUALITY}')

import time


# import threading
from pymavlink import mavutil
import sys 
import tty
import termios




# LensPosition = 10
LensPosition = 2
file_cnt = 0
FOCUS_INC = 0.5

def keyboard_handler(fd, events):
    global LensPosition, file_cnt
    # # This function will be called whenever there is input on stdin
    # message = sys.stdin.readline()
    # print(f"You typed: {message}")
    # This function will be called whenever a key is pressed
    key = os.read(fd, 1)
    print(f"You typed: {key.decode()}")
    if key == b'w':
        LensPosition += FOCUS_INC
        LensPosition = max(0, min(LensPosition, 10))
        focal_distance = 1/(LensPosition+0.00001)
        # picam2.set_controls({'LensPosition': LensPosition})
        print(f"{focal_distance = }  {LensPosition = }")

    if key == b's':
        # clip focal_distance to 0 and 500  (5m)
        LensPosition -= FOCUS_INC
        LensPosition = max(0, min(LensPosition, 10))
        focal_distance = 1/(LensPosition+0.00001)
        # picam2.set_controls({'LensPosition': LensPosition})
        print(f"{focal_distance = }  {LensPosition = }")
        StatusHandler.update_status(f'New file_cnt {file_cnt}')
        file_cnt += 1


    if key == b'q':
        # Stop the loop
        loop.stop()
        # picam2.stop()
        print("********  Stop the loop")



def process_mavlink_data():
    global GLOBAL_POSITION_INT_msg
    # Start a connection listening to a UDP port
    the_connection = mavutil.mavlink_connection('udpin:0.0.0.0:14560')
    # the_connection = mavutil.mavlink_connection('udpin:0.0.0.0:14445')
    # Wait for the first heartbeat 
    # This sets the system and component ID of remote system for the link
    print("Waiting for heartbeat from system")
    the_connection.wait_heartbeat()
    print("Heartbeat from system (system %u component %u)" % (the_connection.target_system, the_connection.target_system))

    # Wait for the vehicle to send GPS_RAW_INT message
    time.sleep(1)

    while True:

        try: 
            # Wait for a GPS_RAW_INT message with a timeout of 10 seconds
            msg = the_connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=10)

            GLOBAL_POSITION_INT_msg = msg

            if msg is not None:
                pass
            else:
                print('No GPS_RAW_INT message received within the timeout period')
        except:
            print('Error while waiting for GPS_RAW_INT message')

# Create a new thread and start it
mavlink_thread = threading.Thread(target=process_mavlink_data, daemon=True)
mavlink_thread.start()

loop = None
KEYBOARD = False
def main():
    global loop, g_RESOLUTION, g_REC_FRAMERATE, g_JPG_QUALITY, g_PORT

    parser = argparse.ArgumentParser(description='Run the Rpi camera app.')
    parser.add_argument('--resolution', '-r', type=float, help='Resolution of the video', default=0.8)
    parser.add_argument('--framerate_record', '-fr', type=int, help='Framerate of the record', default=3)
    parser.add_argument('--framerate_camera', '-fc', type=int, help='Framerate of the camera', default=10)
    parser.add_argument('--jpg_quality', '-q', type=int, help='Quality of the JPEG encoding', default=95)
    parser.add_argument('--port', '-p', type=int, help='Quality of the JPEG encoding', default=8075)

    args = parser.parse_args()

    # Now you can access the values with args.resolution, args.framerate, and args.jpg_quality
    print(args.resolution, args.framerate_record, args.framerate_camera, args.jpg_quality, args.port)
    g_RESOLUTION, g_REC_FRAMERATE, g_CAM_FRAMERATE, g_JPG_QUALITY, g_PORT = args.resolution, args.framerate_record, args.framerate_camera,  args.jpg_quality, args.port

    set_camera()


    
    directory_to_serve = os.path.join(os.path.dirname(__file__), 'static')
    # directory_to_serve = os.path.dirname(__file__)
    directory_to_serve = '/static'

    requestHandlers = [
        (r"/ws/", wsHandler),
        (r"/", indexHandler),
        (r"/center/", centerHandler),
        (r"/grid/", gridHandler),
        (r"/focus/", focusHandler),
        (r"/jmuxer.min.js", jmuxerHandler),
        (r"/sse/", SSEHandler),
        (r"/record", RecordHandler), 
        (r"/filename", FilenameHandler),
        (r"/status/", StatusHandler),

    ]
    resolution = [int(dim * g_RESOLUTION) for dim in picam2.sensor_resolution]
    print(resolution)
    StatusHandler.update_status(f'Resolution = {resolution}, record framerate = {g_REC_FRAMERATE}, JPG Quality = {g_JPG_QUALITY}')




    if KEYBOARD:
        # Save the current terminal settings
        old_settings = termios.tcgetattr(sys.stdin)

    try:
        if KEYBOARD:
            # Set the terminal to unbuffered mode
            tty.setcbreak(sys.stdin.fileno())

        if RUN_CAMERA:
            output = StreamingOutput()
            # encoder = H264Encoder(repeat=True, framerate=framerate, qp=23)
            # encoder = H264Encoder(repeat=True, framerate=15, bitrate=2000000)
            encoder = H264Encoder(repeat=True, framerate=g_CAM_FRAMERATE, qp=20, iperiod=g_CAM_FRAMERATE)
            encoder.output = output
            picam2.start_recording(encoder, output)

        application = tornado.web.Application(requestHandlers)
        try:
            application.listen(g_PORT)
        except Exception as e:
            print(f"Error in application.listen(serverPort) {e}")
            print("is the application running already? , in a service?")
            return
            
        loop = tornado.ioloop.IOLoop.current()

        if RUN_CAMERA:
            output.setLoop(loop)
        if KEYBOARD:
            # Add the keyboard handler to the IOLoop
            loop.add_handler(sys.stdin.fileno(), keyboard_handler, loop.READ)

        loop.start()
    except KeyboardInterrupt:
        if RUN_CAMERA:
            picam2.stop_recording()

        loop.stop()
        print("********  KeyboardInterrupt")
    finally:
        if KEYBOARD:
            print("********  Restore the terminal settings")
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()
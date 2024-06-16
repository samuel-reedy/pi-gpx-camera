"""
    Version:
--------

- gpx_cam v0.0.1
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
from picamera2.outputs import FfmpegOutput
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


# rgb = np.random.randint(low=0, high=255, size=(224, 244, 3)).astype(np.uint8)

# Write it:
# _ = qoi.write("img.qoi", rgb)

# start configuration
serverPort = 8075
wsURL = "ws://my_ip/ws/"
framerate = 15
framerate_encoder = 15
CAM_TYPE = "hq-6mm-CS-pi"
DO_RECORD = False
record_filename = "transect-001"

try:
    picam2 = Picamera2()
    RUN_CAMERA = True
except:
    print("Error in Picamera2, disabling the camera")
    RUN_CAMERA = False

if RUN_CAMERA:
    full_resolution = picam2.sensor_resolution
    # # 0.8 resolution
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

    video_config = picam2.create_video_configuration(main_stream, lores_stream, encode="lores", buffer_count=2)
    picam2.configure(video_config)
    picam2.start()
    picam2.controls.ExposureTime = 20000

colour = (0,255, 0)
origin = (0, 30)
font = cv2.FONT_HERSHEY_SIMPLEX
scale = 1
thickness = 2

GLOBAL_POSITION_INT_msg = None
PRE_CALLBACK = False
if RUN_CAMERA and PRE_CALLBACK:
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

indexHtml = templatize(getFile('index.html'), {'ip':serverIp, 'port':serverPort, 'fps':framerate})

gridHtml = templatize(getFile('grid.html'), {'ip':serverIp, 'port':serverPort, 'fps':framerate,'color':gridColor, 'thickness':gridThickness})
focusHtml = templatize(getFile('focus.html'), {'ip':serverIp, 'port':serverPort, 'fps':framerate, 'color':focusPeakingColor, 'threshold':focusPeakingthreshold})
jmuxerJs = getFile('jmuxer.min.js')

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
        centerHtml = templatize(getFile('center.html'), {'ip':serverIp, 'port':serverPort, 'fps':framerate, 'record_filename':record_filename, 'color':centerColor, 'thickness':centerThickness})
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
        global DO_RECORD, GLOBAL_POSITION_INT_msg, record_filename


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
            self.q = queue.Queue()
            def capture_arr():
                print('Starting capture Thread')
                # Time delay for 3 frames per second
                delay = 1 / 3
                while DO_RECORD:
                    start_time = time.time()
                    arr = picam2.capture_array()
                    self.q.put(arr)
    
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
                            arr = self.q.get()
                            # arr = picam2.capture_array()
                            if GLOBAL_POSITION_INT_msg is not None:
                                text = f'#{frame_count}, {lat}, {lon}, {altitude}'

                                (text_width, text_height) = cv2.getTextSize(text, font, scale, thickness)[0]
                                # Draw a black rectangle under the text
                                cv2.rectangle(arr, (0, 30 - text_height-5), (text_width, 40), (0, 0, 0), -1)
                                cv2.putText(arr, str(text), (0, 30), font, scale, colour, thickness)

                            # is_success, buffer = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, quality])
                            buffer = simplejpeg.encode_jpeg(arr, quality=90, colorspace='RGB', colorsubsampling='420', fastdct=True)
                            output.outputframe(buffer)
                        except queue.Empty:
                            time.sleep(1)
                            # continue
                    else:
                        time.sleep(1)



                    # print(f'Total time taken cv jpg: {time.time()-start_time} seconds')
                    # cv2.imwrite(f'output-q-{quality}.jpg', arr, [cv2.IMWRITE_JPEG_QUALITY, quality])
                        # Increment the frame count
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

            self.cap_thread = threading.Thread(target=capture_arr)
            # Set the thread as a daemon so it will end when the main program ends
            self.cap_thread.daemon = True
            self.cap_thread.start()
            self.rec_thread.start()



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

StatusHandler.update_status('New status')

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


loop = None
KEYBOARD = False
def main():
    global loop
    # Create a new thread and start it
    mavlink_thread = threading.Thread(target=process_mavlink_data, daemon=True)
    mavlink_thread.start()
    
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
            encoder = H264Encoder(repeat=True, framerate=framerate_encoder, qp=20)
            encoder.output = output
            picam2.start_recording(encoder, output)

        application = tornado.web.Application(requestHandlers)
        try:
            application.listen(serverPort)
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
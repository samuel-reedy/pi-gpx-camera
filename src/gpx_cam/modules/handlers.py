import tornado.web, tornado.ioloop, tornado.websocket  
import tornado.gen
import socket
import shutil
import math
import json
import os
import queue
from datetime import datetime
import threading
import time
import shutil
import cv2
import simplejpeg


from .utils import (
    templatize, getFile, set_exposure, set_framerate, set_camera, move_file_to_complete
)
from .classes.config import Config
from .logging import logger

from .classes.ffmpegOutput import FfmpegOutput

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
        
        # Prepare variables for the template
        template_vars = {
            'ip': serverIp,
            'port': Config.PORT,
            'fps': Config.framerate_js,
            'record_filename': Config.record_filename,
            'exposure': Config.cam_exposure,
            'framerate': Config.CAM_FRAMERATE,
            'isRecording': 'true' if Config.isRecording else 'false'
        }
        
        # Render the HTML with the variables
        centerHtml = templatize(getFile('templates/index.html'), template_vars)
        
        # Write the rendered HTML to the response
        self.write(centerHtml)

class thumbnailHandler(tornado.web.RequestHandler):
    def get(self):
        server_host = self.request.host.split(':')[0]  # Split to remove port if present
        serverIp = socket.gethostbyname(server_host)  # Resolve host name to IP
        thumbnailHtml = templatize(getFile('templates/thumbnail.html'), {'ip':serverIp, 'port':Config.PORT, \
                                                        'fps':Config.framerate_js, 'record_filename':Config.record_filename, 'exposure': Config.cam_exposure, 'framerate': Config.CAM_FRAMERATE,\
                                                            'isRecording': 'true' if Config.isRecording else 'false'})
        self.write(thumbnailHtml)



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
                logger.info("Stream is closed")
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
                    logger.warning("Error in StatusHandler", e)
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
        logger.info(f"File {filename}.avi moved to complete folder.")
    except FileNotFoundError:
        logger.error(f"File {filename}.avi not found in data folder.")
    except PermissionError as e:
        logger.error(f"Permission denied while moving file {filename}.avi: {e}")
    print(f"Recording path: {recording_path}")
    print(f"Complete path: {complete_path}")


class RecordHandler(tornado.web.RequestHandler):
    def post(self):
        picam2 = self.application.settings['picam2']
        is_recording = self.get_argument('isRecording') == 'true'
        if is_recording:

            # check for dir and create if needed 
            if not os.path.exists("../../data/recording/"):
                os.makedirs("../../data/recording/")
            
            Config.isRecording = True
            self.cap_que = queue.Queue(maxsize=2)
            self.jpg_que = queue.Queue(maxsize=2)

  
            def capture_arr():
                logger.info('Starting capture Thread')

                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 1
                thickness = 2
                colour = (0,255, 0)
                # Time delay for g_FRAMERATE frames per second
                delay = 1 / Config.REC_FRAMERATE
                logger.debug(f"{Config.REC_FRAMERATE = }")
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
                    logger.debug(f"simple-jpeg encode time = {time.time() - start} {len(buffer) = }")

                    if self.jpg_que.full():
                        self.jpg_que.get() # If the queue is full, remove an item before adding a new one
                    self.jpg_que.put(buffer)
    
                    elapsed_time = time.time() - start_time
                    if elapsed_time < delay:
                        time.sleep(delay - elapsed_time)
      

            # Define your recording logic in a function
            def record(record_filename):
                fn_vid = f'../../data/recording/{record_filename}.avi' if Config.RUN_CAMERA else 'No Camera Found'

                logger.info(f"Recording started to {fn_vid}")

                logger.debug('Starting record Thread')
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
                            logger.error(f"Error in record thread {e}")


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
            logger.info("Recording stopped")
            Config.isRecording = False
            Config.rec_start_position = None
            move_file_to_complete(Config.record_filename)
            # self.thread.join()




class FilenameHandler(tornado.web.RequestHandler):
    def post(self):
        Config.record_filename = self.get_argument('videoFile')
        logger.info(f"Set Record filename: {Config.record_filename }")


class ExposureHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            # Assuming the exposure value is sent as a JSON object {"exposure": value}
            exposure_data = json.loads(self.request.body)
            new_exposure = exposure_data.get('exposure')
            picam2 = self.application.settings['picam2']

            if new_exposure is not None:

                set_exposure(new_exposure, picam2)
                self.write({"status": "success", "message": "Exposure updated successfully."})
            else:
                self.set_status(400)  # Bad Request
                self.write({"status": "error", "message": "Invalid exposure value."})
        except Exception as e:
            logger.error(f"Error updating exposure: {e}")
            self.set_status(500)  # Internal Server Error
            self.write({"status": "error", "message": "Failed to update exposure."})
        self.finish()


class FramerateHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            # Assuming the framerate value is sent as a JSON object {"framerate": value}
            framerate_data = json.loads(self.request.body)
            new_framerate = framerate_data.get('framerate')
            picam2 = self.application.settings['picam2']

            if new_framerate is not None:

                set_framerate(new_framerate, picam2)
                self.write({"status": "success", "message": "Framerate updated successfully."})
            else:
                self.set_status(400)  # Bad Request
                self.write({"status": "error", "message": "Invalid framerate value."})
        except Exception as e:
            logger.error(f"Error updating framerate: {e}")
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
                logger.debug("Stream is closed")
                # break out of generator loop
                break
            try:
                self.write(f"data: {self.status} \n\n")
                await self.flush()
            except Exception as e:
                logger.error("Error in SSEHandler", e)
                pass
            await tornado.gen.sleep(1)  # Wait for 1 second

    @classmethod
    def update_status(cls, status):
        cls.status = status

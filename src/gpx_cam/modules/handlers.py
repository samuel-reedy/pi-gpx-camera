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
import gpxpy
import gpxpy.gpx

import piexif


from .utils import (
    templatize, getFile, set_exposure, set_framerate, set_camera, move_file_to_complete, 
    move_file_to_complete, inject_gps_data
)

from .logging import logger

from .classes.ffmpegOutput import FfmpegOutput

from .classes.configHandler import config

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
        
        template_vars = {
            'ip': serverIp,
            'port': config.get('PORT'),
            'fps': config.get('CAM_FRAMERATE'),
            'record_filename': config.get('RECORD_FILENAME'),
            'exposure': config.get('CAM_EXPOSURE'),
            'isRecording': 'true' if config.get('IS_RECORDING') else 'false'
        }
        
        centerHtml = templatize(getFile('templates/index.html'), template_vars)
        self.write(centerHtml)

class thumbnailHandler(tornado.web.RequestHandler):
    def get(self):
        server_host = self.request.host.split(':')[0]  # Split to remove port if present
        serverIp = socket.gethostbyname(server_host)  # Resolve host name to IP
        
        template_vars = {
            'ip': serverIp,
            'port': config.get('PORT'),
            'fps': config.get('CAM_FRAMERATE'),
            'record_filename': config.get('RECORD_FILENAME'),
            'exposure': config.get('CAM_EXPOSURE'),
            'isRecording': 'true' if config.get('IS_RECORDING') else 'false'
        }
        

        thumbnailHtml = templatize(getFile('templates/thumbnail.html'), template_vars)
        self.write(thumbnailHtml)

class parametersHandler(tornado.web.RequestHandler):
    def get(self):
        server_host = self.request.host.split(':')[0]  # Split to remove port if present
        serverIp = socket.gethostbyname(server_host)  # Resolve host name to IP
        
        msg = config.get('MAV_MSG_GLOBAL_POSITION_INT')

        # Extract relevant variables from config
        if (msg is not None):
            lat = msg['lat'] / 1.0e7
            lon = msg['lon'] / 1.0e7
            alt = msg['alt'] / 1000
            relative_alt = msg['relative_alt'] / 1000
            vx = msg['vx'] / 100
            vy = msg['vy'] / 100
            vz = msg['vz'] / 100
            hdg = msg['hdg'] / 1000
        else:
            lat = 0
            lon = 0
            alt = 0
            relative_alt = 0
            vx = 0
            vy = 0
            vz = 0
            hdg = 0

        template_vars = {
            'ip': serverIp,
            'port': config.get('PORT'),
            'wsURL': config.get('WS_URL'),
            'cam_type': config.get('CAM_TYPE'),
            'run_camera': config.get('RUN_CAMERA'),
            'is_recording': config.get('IS_RECORDING'),
            'store_gpx': config.get('STORE_GPX'),
            'rec_start_position': config.get('REC_START_POSITION'),
            'record_filename': config.get('RECORD_FILENAME'),
            'resolution': config.get('RESOLUTION'),
            'rec_framerate': config.get('REC_FRAMERATE'),
            'cam_framerate': config.get('CAM_FRAMERATE'),
            'jpg_quality': config.get('JPG_QUALITY'),
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'relative_alt': relative_alt,
            'vx': vx,
            'vy': vy,
            'vz': vz,
            'hdg': hdg,
            'mav_satellites_visible': config.get('MAV_SATELLITES_VISIBLE'),
            'framerate_js': config.get('FRAMERATE_JS'),
            'cam_exposure': config.get('CAM_EXPOSURE'),
            'stream_resolution': config.get('STREAM_RESOLUTION'),
            'ideal_depth': config.get('GAUGE.IDEAL_DEPTH'),
            'min_radius': config.get('GAUGE.MIN_RADIUS'),
            'max_radius': config.get('GAUGE.MAX_RADIUS'),
            'max_depth_difference': config.get('GAUGE.MAX_DEPTH_DIFFERENCE'),
            'rec_time': config.get('REC_TIME')
        }

        parametersHtml = templatize(getFile('templates/parameters.html'), template_vars)
        self.write(parametersHtml)


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
        if config.get('MAV_MSG_GLOBAL_POSITION_INT') is not None:
            msg = config.get('MAV_MSG_GLOBAL_POSITION_INT')
            n_satellites = config.get('MAV_SATELLITES_VISIBLE')

            if config.get('REC_START_POSITION') is not None:
                altitude = msg['alt'] / 1000.0
                start_lat, start_lon, start_alt = config.get('REC_START_POSITION')
                east, north = gps_to_meters_east_north(start_lat, start_lon, msg['lat']/1.0e7, msg['lon']/1.0e7)
                data = {"latlon": f"East: {east:.1f}, North: {north:.1f}, altitude: {altitude}, Satellites: {n_satellites}"}                      
            else:
                altitude = msg['alt'] / 1000.0
                lat = msg['lat'] / 1.0e7
                lon = msg['lon'] / 1.0e7
                
                data = {
                    'altitude': altitude,
                    'latitude': lat,
                    'longitude': lon
                }
            return data
        return None
    
    def _get_record_state(self):
        return {"isRecording": config.get('IS_RECORDING')}
    def _get_status(self):
        return {"status": self.status}

    def _get_record_filename(self):
        return {"record_filename": config.get('RECORD_FILENAME')}
    
    def _get_record_time(Self):
        return {"rec_time": config.get('REC_TIME')}
    
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
                data.update(self._get_record_time())
                data = json.dumps(data)
                try:
                    self.write(f"data: {data} \n\n")
                    self.count += 1
                    await self.flush()  # Flush the data to the client
                except Exception as e:
                    logger.warning("Error in StatusHandler", e)
                    pass

            await tornado.gen.sleep(0.2)  # Wait for 1 second

    @classmethod
    def update_status(cls, status):
        cls.status = status




class RecordHandler(tornado.web.RequestHandler):
    def post(self):
        picam2 = self.application.settings['picam2']
        is_recording = self.get_argument('isRecording') == 'true'
        if is_recording:

            # check for dir and create if needed 
            if not os.path.exists("../../data/recording/"):
                os.makedirs("../../data/recording/")
            
            config.set('IS_RECORDING', True)
            self.jpg_que = queue.Queue(maxsize=2)

            begin_time = time.perf_counter()

            def capture_arr():
                logger.info('Starting capture Thread')
                
                # Time delay for g_FRAMERATE frames per second
                frame_interval = 1 / config.get('REC_FRAMERATE')
                logger.debug(f"{config.get('REC_FRAMERATE') = }")

                while config.get('IS_RECORDING'):
                    start_time = time.perf_counter()

                    arr = picam2.capture_array()
                    buffer = simplejpeg.encode_jpeg(arr, quality=config.get('JPG_QUALITY'), colorspace='RGB', colorsubsampling='420', fastdct=True)

                    if config.get('MAV_MSG_GLOBAL_POSITION_INT') is not None:
                        msg = config.get('MAV_MSG_GLOBAL_POSITION_INT')
                        buffer = inject_gps_data(buffer, msg)

                    if self.jpg_que.full():
                        self.jpg_que.get()  # If the queue is full, remove an item before adding a new one
                    self.jpg_que.put(buffer)

                    config.set('REC_TIME', time.perf_counter() - begin_time)
                    # Calculate the time to sleep to maintain the desired framerate
                    elapsed_time = time.perf_counter() - start_time
                    sleep_time = frame_interval - elapsed_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)
      

            # Define your recording logic in a function
            def record(record_filename):
                fn_vid = f'../../data/recording/{record_filename}.avi' if config.get('RUN_CAMERA') else 'No Camera Found'
                logger.info(f"Recording started to {fn_vid}")
                
                
                fn_gpx = f"../../data/recording/{record_filename}.gpx" if config.get('MAV_MSG_GLOBAL_POSITION_INT') else 'No position MAV messages found'

                if config.get('MAV_MSG_GLOBAL_POSITION_INT') is not None and config.get('STORE_GPX'):
                    gpx = gpxpy.gpx.GPX()

                    # Create a new track in our GPX file
                    gpx_track = gpxpy.gpx.GPXTrack(name='transect', description='transect description')
                    gpx.tracks.append(gpx_track)

                    # Create first segment in our GPX track:
                    gpx_segment = gpxpy.gpx.GPXTrackSegment()
                    gpx_track.segments.append(gpx_segment)

                    msg = config.get('MAV_MSG_GLOBAL_POSITION_INT')
                    print(msg)
                    config.set('REC_START_POSITION', (msg["lat"]/1.0e7, msg["lon"]/1.0e7, msg["alt"]/1000.0))

                    print("Starting GPX track")
                    logger.info(f"Recording started to {fn_gpx}")

                

                logger.debug('Starting record Thread')

                quality = 90
                if config.get('RUN_CAMERA'):
                    output = FfmpegOutput(fn_vid,)
                    output.start()
                fps = 0
                frame_count = 0
                start_time = time.time()
                last_time = start_time
                while config.get('IS_RECORDING'):      
                    
                    if config.get('MAV_MSG_GLOBAL_POSITION_INT') is not None and config.get('STORE_GPX'):
                        msg = config.get('MAV_MSG_GLOBAL_POSITION_INT')
                        altitude = msg["alt"] / 1000.0
                        lat = msg["lat"] / 1.0e7
                        lon = msg["lon"]/ 1.0e7
                        n_satellites = config.get('MAV_SATELLITES_VISIBLE')
                        str_n_sats = f'Satellites: {n_satellites}'
                        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon, elevation=altitude, time=datetime.now(), comment=str_n_sats, speed=n_satellites, symbol='Waypoint'))
                        # todo add photo frame number`


                    if config.get('RUN_CAMERA'):
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

                    # on every second
                    if time.time() - last_time > 1: 
                        last_time = time.time()


                if config.get('RUN_CAMERA'):
                    output.stop()
                if config.get('STORE_GPX'):
                    with open(fn_gpx, 'w') as f:
                        f.write(gpx.to_xml())

            # Create and start a thread running the record function
            self.rec_thread = threading.Thread(target=record, args=(config.get('RECORD_FILENAME'),))
            self.rec_thread.daemon = True
            self.rec_thread.start()

            if config.get('RUN_CAMERA'):
                self.cap_thread = threading.Thread(target=capture_arr)
                self.cap_thread.daemon = True
                self.cap_thread.start()

        else:
            logger.info("Recording stopped")
            config.set('IS_RECORDING', False)
            config.set('REC_START_POSITION', None)
            move_file_to_complete(str(config.get('RECORD_FILENAME')), ".avi")
            if (config.get('STORE_GPX')):
                move_file_to_complete(str(config.get('RECORD_FILENAME')), ".gpx")


class FilenameHandler(tornado.web.RequestHandler):
    def post(self):
        config.set('RECORD_FILENAME', self.get_argument('videoFile'))
        logger.info(f"Set Record filename: {config.get('RECORD_FILENAME')}")


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



class SettingsHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)

            picam2 = self.application.settings['picam2']

            record_filename = data.get('record_filename')
            resolution = float(data.get('resolution'))
            jpg_quality = int(data.get('jpg_quality'))
            cam_exposure = int(data.get('cam_exposure'))
            cam_framerate = int(data.get('cam_framerate'))
            rec_framerate = int(data.get('rec_framerate'))
            
            ideal_depth = float(data.get('ideal_depth'))
            min_radius = int(data.get('min_radius'))
            max_radius = int(data.get('max_radius'))
            max_depth_difference = int(data.get('max_depth_difference', 3))

            store_gpx = data.get('store_gpx')
            
            if str(store_gpx).lower() == 't' or str(store_gpx).lower() == 'true':
                config.set("STORE_GPX", True)
            else:
                config.set("STORE_GPX", False)

            if cam_exposure is not None:
                set_exposure(cam_exposure, picam2)

            if cam_framerate is not None:
                set_framerate(cam_framerate, picam2)

            if rec_framerate is not None:
                config.set("REC_FRAMERATE", rec_framerate)

            if record_filename is not None:
                config.set("RECORD_FILENAME", record_filename)

            if resolution is not None:
                config.set("RESOLUTION", resolution)

            if jpg_quality is not None:
                config.set("JPG_QUALITY", jpg_quality)

            if ideal_depth is not None:
                config.set("GAUGE.IDEAL_DEPTH", ideal_depth)

            if min_radius is not None:
                config.set("GAUGE.MIN_RADIUS", min_radius)

            if max_radius is not None:
                config.set("GAUGE.MAX_RADIUS", max_radius)

            if max_depth_difference is not None:
                config.set("GAUGE.MAX_DEPTH_DIFFERENCE", max_depth_difference)

            self.write({"status": "success", "message": "Settings updated"})
        except Exception as e:
            logger.error("Error processing request: %s", str(e))
            self.set_status(400)
            self.write({"status": "error", "message": str(e)})
        self.finish()

    def get(self):
        try:
            self.write({
                "status": "success",
                "data": {
                    "ideal_depth": config.get("GAUGE.IDEAL_DEPTH"),
                    "min_radius": config.get("GAUGE.MIN_RADIUS"),
                    "max_radius": config.get("GAUGE.MAX_RADIUS"),
                    "max_depth_difference": config.get("GAUGE.MAX_DEPTH_DIFFERENCE"),
                    "cam_framerate": config.get("CAM_FRAMERATE"),
                    "cam_exposure": config.get("CAM_EXPOSURE")
                }
            })
        except Exception as e:
            logger.error(f"Error retrieving gauge parameters: {e}")
            self.set_status(500)  # Internal Server Error
            self.write({"status": "error", "message": "Failed to retrieve gauge parameters."})
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

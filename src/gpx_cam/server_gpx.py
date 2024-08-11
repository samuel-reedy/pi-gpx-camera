import time
import threading
import argparse
import os
import sys 
import tty
import termios

from .modules.classes.streamingOutput import StreamingOutput
from .modules.classes.cameraState import cameraState
from .modules.classes.mavlinkMessages import mavlinkMessages
from .modules.logging import logger
from .modules.classes.configHandler import config
from .modules.utils import set_camera
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder

import tornado.web
import tornado.ioloop
import tornado.websocket
import tornado.gen
from tornado.ioloop import PeriodicCallback

from .modules.handlers import (
    wsHandler, indexHandler, jmuxerHandler, thumbnailHandler, parametersHandler, SettingsHandler,
    RecordHandler, FilenameHandler, ExposureHandler, FramerateHandler
)

try:
    picam2 = Picamera2()
    cameraState.RUN_CAMERA = True
except:
    logger.error("Error in Picamera2, disabling the camera")
    cameraState.RUN_CAMERA = False


abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)



# LensPosition = 10
LensPosition = 2
file_cnt = 0
FOCUS_INC = 0.5
    


def update_status_periodically(camera):
    cameraState.get_metadata(camera)
        
            

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
    config.set('RESOLUTION', args.resolution)
    config.set('REC_FRAMERATE', args.framerate_record)
    config.set('JPG_QUALITY', args.jpg_quality)
    config.set('PORT', args.port)
    config.set('MAVPORT', args.mavport)

    logger.info(f"{config.get('RESOLUTION') = }, {config.get('REC_FRAMERATE') = }, {config.get('CAM_FRAMERATE') = }, \
          {config.get('JPG_QUALITY') = }, {config.get('PORT') = }, {config.get('MAVPORT') = }")

    set_camera(picam2, config.get('STREAM_RESOLUTION'))
    

    # Create a new thread and start it
    mavlink_thread = threading.Thread(target=mavlinkMessages.process_mavlink_data, daemon=True)
    mavlink_thread.start()

    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    
    # directory_to_serve = os.path.join(os.path.dirname(__file__), 'static')
    # directory_to_serve = os.path.dirname(__file__)
    # directory_to_serve = '/static'

    requestHandlers = [
        (r"/ws/", wsHandler),
        (r"/center", indexHandler),
        (r"/thumbnail", thumbnailHandler),
        (r"/parameters", parametersHandler),
        (r"/jmuxer.min.js", jmuxerHandler),
        (r"/record", RecordHandler), 
        (r"/filename", FilenameHandler),
        (r"/set-exposure", ExposureHandler),
        (r"/set-framerate", FramerateHandler), 
        (r"/settings", SettingsHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static_dir}), 
        (r"/", indexHandler),    # this one is last so not to interfere with the above routes
    ]

    
    status_update_callback = PeriodicCallback(lambda: update_status_periodically(picam2), 1000)  # 1000 ms = 1 second
    status_update_callback.start()
    

    if KEYBOARD:
        # Save the current terminal settings
        old_settings = termios.tcgetattr(sys.stdin)

    try:
        if KEYBOARD:
            # Set the terminal to unbuffered mode
            tty.setcbreak(sys.stdin.fileno())

        if cameraState.RUN_CAMERA:
            output = StreamingOutput()
            encoder = H264Encoder(repeat=True, framerate=config.get('CAM_FRAMERATE'), qp=20, iperiod=config.get('CAM_FRAMERATE'))
            encoder.output = output
            picam2.start_recording(encoder, output)

        application = tornado.web.Application(requestHandlers, picam2=picam2)
        try:
            application.listen(config.get('PORT'))
        except Exception as e:
            logger.error(f"Error in application.listen(serverPort) {e}")
            logger.error("is the application running already? , in a service?")
            return
            
        loop = tornado.ioloop.IOLoop.current()

        if cameraState.RUN_CAMERA:
            output.setLoop(loop)

        loop.start()
    except KeyboardInterrupt:
        if cameraState.RUN_CAMERA:
            picam2.stop_recording()

        loop.stop()
        # print("********  KeyboardInterrupt")
    finally:
        if KEYBOARD:
            # print("********  Restore the terminal settings")
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()
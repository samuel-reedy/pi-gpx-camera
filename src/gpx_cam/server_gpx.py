"""
    Version:
--------


"""

import os

import tornado.web, tornado.ioloop, tornado.websocket  
import tornado.gen


from .modules.logging import logger

try:
    # assert False
    from picamera2 import Picamera2, MappedArray
    from picamera2.encoders import H264Encoder

except:
    logger.error("Error in Picamera2, disabling the camera")


from pymavlink import mavutil
import time
import threading


import argparse

from .modules.handlers import (
    wsHandler, indexHandler, jmuxerHandler, thumbnailHandler, parametersHandler,
    RecordHandler, FilenameHandler, StatusHandler, ExposureHandler, FramerateHandler, SettingsHandler
)

from .modules.utils import (
    set_camera
)

from .modules.classes.streamingOutput import StreamingOutput
from .modules.classes.gauge import Gauge



from .modules.classes.configHandler import config


try:
    # assert False
    picam2 = Picamera2()
    config.set('RUN_CAMERA', True)
except:
    logger.error("Error in Picamera2, disabling the camera")
    config.set('RUN_CAMERA', False)



abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

from pymavlink import mavutil
import sys 
import tty
import termios


# LensPosition = 10
LensPosition = 2
file_cnt = 0
FOCUS_INC = 0.5



def process_mavlink_data():
    print("Starting process_mavlink_data")
    logger.info("Starting process_mavlink_data")
    
    try:
        # Start a connection listening to a UDP port
        the_connection = mavutil.mavlink_connection(f"udpin:0.0.0.0:{config.get('MAVPORT')}")
        # the_connection = mavutil.mavlink_connection('udpin:0.0.0.0:14445')
        # Wait for the first heartbeat 
        # This sets the system and component ID of remote system for the link
        logger.info("Waiting for heartbeat from system")
        the_connection.wait_heartbeat()
        logger.info("Heartbeat from system (system %u component %u)" % (the_connection.target_system, the_connection.target_system))

        time.sleep(1)
        # Wait for the vehicle to send GPS_RAW_INT message
        the_connection.mav.param_request_list_send(
            the_connection.target_system, the_connection.target_component
        )

        while True:
            msg = the_connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=10)
            if msg is not None:
                logger.debug(f"Received GLOBAL_POSITION_INT: {msg}")
                # Convert msg to a dictionary
                msg_dict = {
                    'time_boot_ms': msg.time_boot_ms,
                    'lat': msg.lat,
                    'lon': msg.lon,
                    'alt': msg.alt,
                    'relative_alt': msg.relative_alt,
                    'vx': msg.vx,
                    'vy': msg.vy,
                    'vz': msg.vz,
                    'hdg': msg.hdg
                }
                config.set('MAV_MSG_GLOBAL_POSITION_INT', msg_dict)
            else:
                logger.debug("No GLOBAL_POSITION_INT message received")

            msg = the_connection.recv_match(type='GPS_RAW_INT', blocking=True, timeout=10)
            if msg is not None:
                config.set('MAV_SATELLITES_VISIBLE', msg.satellites_visible)
            else:
                logger.info('No GPS_RAW_INT message received within the timeout period')
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")

    


def update_status_periodically():

    while True:
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

    config.set('RESOLUTION', args.resolution)
    config.set('REC_FRAMERATE', args.framerate_record)
    config.set('JPG_QUALITY', args.jpg_quality)
    config.set('PORT', args.port)
    config.set('MAVPORT', args.mavport)

    logger.info(f"{config.get('RESOLUTION') = }, {config.get('REC_FRAMERATE') = }, {config.get('CAM_FRAMERATE') = }, \
          {config.get('JPG_QUALITY') = }, {config.get('PORT') = }, {config.get('MAVPORT') = }")

    set_camera(picam2, config.get('STREAM_RESOLUTION'))
    

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
        (r"/thumbnail", thumbnailHandler),
        (r"/parameters", parametersHandler),
        (r"/jmuxer.min.js", jmuxerHandler),
        (r"/record", RecordHandler), 
        (r"/filename", FilenameHandler),
        (r"/status/", StatusHandler),
        (r"/set-exposure", ExposureHandler),
        (r"/set-framerate", FramerateHandler), 
        (r"/settings", SettingsHandler),
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

        if config.get('RUN_CAMERA'):
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

        if config.get('RUN_CAMERA'):
            output.setLoop(loop)

        loop.start()
    except KeyboardInterrupt:
        if config.get('RUN_CAMERA'):
            picam2.stop_recording()

        loop.stop()
        # print("********  KeyboardInterrupt")
    finally:
        if KEYBOARD:
            # print("********  Restore the terminal settings")
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()
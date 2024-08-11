# utils.py
import os
import shutil
from string import Template
import piexif
from PIL import Image
import io
from fractions import Fraction
import json



from .classes.configHandler import config
from .classes.cameraState import cameraState

from .logging import logger
try:
    # assert False
    from picamera2 import Picamera2, MappedArray
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import Output
    import prctl
    import cv2
    import simplejpeg  # simplejpeg is a simple package based on recent versions of libturbojpeg for fast JPEG encoding and decoding.
except:
    logger.error("Error in Picamera2, disabling the camera")

def templatize(content, replacements):
    tmpl = Template(content)
    return tmpl.substitute(replacements)

def getFile(filePath):
    file = open(filePath,'r')
    content = file.read()
    file.close()
    return content

def set_exposure(exposure, cam):
    if cameraState.RUN_CAMERA:
        # clip 100 to 20000
        exposure = max(100, min(exposure, 20000))
        config.set('CAM_EXPOSURE', exposure)
        cam.set_controls({'ExposureTime': config.get('CAM_EXPOSURE')})
        logger.debug(f"Set new exposure: {config.get('CAM_EXPOSURE')}")

def set_framerate(exposure, cam):
    if cameraState.RUN_CAMERA:
        framerate = max(1, min(exposure, 30))
        config.set('CAM_FRAMERATE', framerate)
        cam.set_controls({'FrameRate': config.get('CAM_FRAMERATE')})
        logger.debug(f"Set new framerate: {config.get('CAM_FRAMERATE')}")

def set_camera(cam, stream_resolution):
    if cameraState.RUN_CAMERA:

        resolution = [int(dim * config.get('RESOLUTION')) for dim in cam.sensor_resolution]
        main_stream = {'format': 'BGR888', 'size': resolution}
        lores_stream = {"size": (stream_resolution["WIDTH"], stream_resolution["HEIGHT"])}
        # lores_stream = {"size": (1280, 960)}
        # lores_stream = {"size": (1920, 1080)}

        logger.info(f"{main_stream = }")
        logger.info(f"{lores_stream = }")

        video_config = cam.create_video_configuration(main_stream, lores_stream, encode="lores", buffer_count=3)
        cam.configure(video_config)
        cam.start()
        # picam2.controls.ExposureTime = 20000
        # picam2.set_controls({"ExposureTime": 20000, "FrameRate": Config.CAM_FRAMERATE})
        cam.set_controls({"AeExposureMode": 1, "FrameRate": config.get('CAM_FRAMERATE')})    # 1 = short https://libcamera.org/api-html/namespacelibcamera_1_1controls.html
        set_exposure(config.get('CAM_EXPOSURE'), cam)
        set_framerate(config.get('CAM_FRAMERATE'), cam)



def move_file_to_complete(filename, file_type):
    data_folder = os.path.abspath("../../data")

    if (file_type==".gpx"):
        complete_folder = os.path.join(data_folder, "complete/gpx")
    else:
        complete_folder = os.path.join(data_folder, "complete/avi")
    recording_folder = os.path.join(data_folder, "recording")

   
    recording_path = os.path.join(recording_folder, filename + file_type)
    complete_path = os.path.join(complete_folder, filename + file_type)

    logger.info(f"Recording Path: {recording_path}, Complete Path: {complete_path}")


    if not os.path.exists(complete_folder):
        os.makedirs(complete_folder)
        logger.info(f"{complete_folder} folder created.")

    try:
        if os.path.exists(complete_path):
            i = 1
            new_filename = filename + f"({i})" + file_type
            while os.path.exists(os.path.join(complete_folder, new_filename)):
                i += 1
                old_filename = new_filename
                new_filename = filename + f"({i})" + file_type
                logger.info(f"File {old_filename} already exists in complete folder. Renaming to {new_filename}")
            complete_path = os.path.join(complete_folder, new_filename)

        shutil.move(recording_path, complete_path)
        logger.info(f"File moved to complete folder.")

        logger.error(f"File {complete_path} not found in data folder.")
    except FileNotFoundError as e:
        logger.error(f"File {complete_path} not found in data folder: {e}")
    except PermissionError as e:
        logger.error(f"Permission denied while moving file {filename}: {e}")



def deg_to_dms(decimal_coordinate, cardinal_directions):
    if decimal_coordinate < 0:
        compass_direction = cardinal_directions[0]
    elif decimal_coordinate > 0:
        compass_direction = cardinal_directions[1]
    else:
        compass_direction = ""
    degrees = int(abs(decimal_coordinate))
    decimal_minutes = (abs(decimal_coordinate) - degrees) * 60
    minutes = int(decimal_minutes)
    seconds = Fraction((decimal_minutes - minutes) * 60).limit_denominator(100)
    return degrees, minutes, seconds, compass_direction

def dms_to_exif_format(dms_degrees, dms_minutes, dms_seconds):
    exif_format = (
        (dms_degrees, 1),
        (dms_minutes, 1),
        (int(dms_seconds.limit_denominator(100).numerator), int(dms_seconds.limit_denominator(100).denominator))
    )
    return exif_format


def inject_gps_data(image_bytes, msg):
    try:
        

        latitude = msg['lat'] / 1e7
        longitude = msg['lon'] / 1e7

        logger.debug(f"Injecting GPS data: lat={latitude}, lon={longitude}")

        # Convert the latitude and longitude coordinates to DMS
        latitude_dms = deg_to_dms(latitude, ["S", "N"])
        longitude_dms = deg_to_dms(longitude, ["W", "E"])

        # Convert the DMS values to EXIF values
        exif_latitude = dms_to_exif_format(latitude_dms[0], latitude_dms[1], latitude_dms[2])
        exif_longitude = dms_to_exif_format(longitude_dms[0], longitude_dms[1], longitude_dms[2])

        exif_data = piexif.load((image_bytes))

        # Create the GPS EXIF data
        coordinates = {
            piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
            piexif.GPSIFD.GPSLatitude: exif_latitude,
            piexif.GPSIFD.GPSLatitudeRef: latitude_dms[3],
            piexif.GPSIFD.GPSLongitude: exif_longitude,
            piexif.GPSIFD.GPSLongitudeRef: longitude_dms[3]
        }

        # Update the EXIF data with the GPS information
        exif_data['GPS'] = coordinates

        # Dump the updated EXIF data and insert it into the image
        exif_bytes = piexif.dump(exif_data)
        output_buffer = io.BytesIO()
        piexif.insert(exif_bytes, image_bytes, output_buffer)
        output_buffer.seek(0)

        output_bytes = output_buffer.getvalue()
        output_exif_data = piexif.load((output_bytes))

        return output_bytes
    except Exception as e:
        logger.error(f"Error injecting GPS data: {e}")
        return image_bytes
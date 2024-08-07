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
    if config.get('RUN_CAMERA'):
        # clip 100 to 20000
        exposure = max(100, min(exposure, 20000))
        config.set('CAM_EXPOSURE', exposure)
        cam.set_controls({'ExposureTime': config.get('CAM_EXPOSURE')})
        logger.debug(f"Set new exposure: {config.get('CAM_EXPOSURE')}")

def set_framerate(exposure, cam):
    if config.get('RUN_CAMERA'):
        framerate = max(1, min(exposure, 30))
        config.set('CAM_FRAMERATE', framerate)
        cam.set_controls({'FrameRate': config.get('CAM_FRAMERATE')})
        logger.debug(f"Set new framerate: {config.get('CAM_FRAMERATE')}")

def set_camera(cam, stream_resolution):
    if config.get('RUN_CAMERA'):

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
    except PermissionError as e:
        logger.error(f"Permission denied while moving file {filename}: {e}")




def convert_to_degrees(value):
    degrees = int(value)
    minutes = int((value - degrees) * 60)

    seconds = (value - degrees - minutes / 60) * 3600
    return ((degrees, 1), (minutes, 1), (int(seconds * 100), 100))


def inject_gps_data(image_bytes, msg):
    lat = msg.lat
    lon = msg.lon

    # Convert latitude and longitude to EXIF format
    lat_ref = 'N' if lat >= 0 else 'S'
    lon_ref = 'E' if lon >= 0 else 'W'

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: convert_to_degrees(abs(lat / 1e7)),
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: convert_to_degrees(abs(lon / 1e7)),
    }

    # Create a new EXIF data structure
    exif_dict = {"0th": {}, "Exif": {}, "GPS": gps_ifd, "Interop": {}, "1st": {}, "thumbnail": None}

    # Convert the EXIF data to binary format
    exif_bytes = piexif.dump(exif_dict)

    # Load the image from bytes
    img = Image.open(io.BytesIO(image_bytes))

    # Save the image to a bytes buffer with the new EXIF data
    output_buffer = io.BytesIO()
    img.save(output_buffer, format=img.format, exif=exif_bytes)
    output_buffer.seek(0)
    
    return output_buffer.getvalue()
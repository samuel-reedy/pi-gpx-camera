# utils.py
import os
import shutil
from string import Template
from .classes.config import Config
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
    if Config.RUN_CAMERA:
        # clip 100 to 20000
        exposure = max(100, min(exposure, 20000))
        Config.cam_exposure = exposure
        cam.set_controls({'ExposureTime': Config.cam_exposure})
        logger.debug(f"Set new exposure: {Config.cam_exposure}")

def set_framerate(exposure, cam):
    if Config.RUN_CAMERA:
        framerate = max(1, min(exposure, 30))
        Config.CAM_FRAMERATE = framerate
        cam.set_controls({'FrameRate': Config.CAM_FRAMERATE})
        logger.debug(f"Set new framerate: {Config.CAM_FRAMERATE}")

def set_camera(cam, stream_resolution):
    if Config.RUN_CAMERA:

        resolution = [int(dim * Config.RESOLUTION) for dim in cam.sensor_resolution]
        main_stream = {'format': 'BGR888', 'size': resolution}
        lores_stream = {"size": (stream_resolution["width"], stream_resolution["height"])}
        # lores_stream = {"size": (1280, 960)}
        # lores_stream = {"size": (1920, 1080)}

        logger.info(f"{main_stream = }")
        logger.info(f"{lores_stream = }")

        video_config = cam.create_video_configuration(main_stream, lores_stream, encode="lores", buffer_count=3)
        cam.configure(video_config)
        cam.start()
        # picam2.controls.ExposureTime = 20000
        # picam2.set_controls({"ExposureTime": 20000, "FrameRate": Config.CAM_FRAMERATE})
        cam.set_controls({"AeExposureMode": 1, "FrameRate": Config.CAM_FRAMERATE})    # 1 = short https://libcamera.org/api-html/namespacelibcamera_1_1controls.html
        set_exposure(2000, cam)
        set_framerate(Config.CAM_FRAMERATE, cam)


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

            cam.post_callback = apply_timestamp

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
            logger.info(f"File {filename}.avi already exists in complete folder. Renaming to {filename}({i}).avi")
        shutil.move(recording_path, complete_path)
        logger.info(f"File {filename}.avi moved to complete folder.")
    except FileNotFoundError:
        logger.error(f"File {filename}.avi not found in data folder.")
    except PermissionError as e:
        logger.error(f"Permission denied while moving file {filename}.avi: {e}")





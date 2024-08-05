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
    STREAM_RESOLUTION = {
        "width": 640,
        "height": 480
    }
    PORT = None # set by params
    mav_msg_GLOBAL_POSITION_INT = None 
    mav_satellites_visible = 0
    # resolution = [0, 0]
    framerate_js = CAM_FRAMERATE
    cam_exposure = None
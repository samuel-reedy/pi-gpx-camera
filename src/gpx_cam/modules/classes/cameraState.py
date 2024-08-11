class CameraState:
    RUN_CAMERA = False
    IS_RECORDING = False
    REC_TIME = 0
    ANALOG_GAIN = 0
    DIGITAL_GAIN = 0

    def get_metadata(self, camera):
        md = camera.capture_metadata()
        cameraState.ANALOG_GAIN = md["AnalogueGain"]
        cameraState.DIGITAL_GAIN = md["DigitalGain"]

cameraState = CameraState()
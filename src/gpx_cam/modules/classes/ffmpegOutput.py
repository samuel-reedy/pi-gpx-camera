import subprocess
from ..logging import logger
import prctl
from picamera2.outputs import Output
import signal
from ..classes.config import Config

class FfmpegOutput(Output):
    """
    The FfmpegOutput class allows an encoded video stream to be passed to FFmpeg for output.
    """

    def __init__(self, output_filename, audio=False, audio_device="default", audio_sync=-0.3,
                audio_samplerate=48000, audio_codec="aac", audio_bitrate=128000, pts=None):
        super().__init__(pts=pts)
        self.ffmpeg = None
        self.output_filename = output_filename
        self.timeout = 1 if audio else None
        # A user can set this to get notifications of FFmpeg failures.
        self.error_callback = None
        # We don't understand timestamps, so an encoder may have to pace output to us.
        self.needs_pacing = True

    def start(self):
        general_options = ['-loglevel', 'warning',
                        '-y', '-f', 'mjpeg']  # -y means overwrite output without asking, -f mjpeg means force input to mjpeg
        # We have to get FFmpeg to timestamp the video frames as it gets them. This isn't
        # ideal because we're likely to pick up some jitter, but works passably, and I
        # don't have a better alternative right now.
        video_input = ['-use_wallclock_as_timestamps', '1',
                    '-thread_queue_size', '64',  # necessary to prevent warnings
                    '-i', '-']
        video_codec = ['-c:v', 'copy']
        command = ['ffmpeg'] + general_options + video_input + \
            video_codec + self.output_filename.split()
        # The preexec_fn is a slightly nasty way of ensuring FFmpeg gets stopped if we quit
        # without calling stop() (which is otherwise not guaranteed).
        self.ffmpeg = subprocess.Popen(command, stdin=subprocess.PIPE, preexec_fn=lambda: prctl.set_pdeathsig(signal.SIGKILL))
        super().start()

    def stop(self):
        super().stop()
        if self.ffmpeg is not None:
            self.ffmpeg.stdin.close()  # FFmpeg needs this to shut down tidily
            try:
                # Give it a moment to flush out video frames, but after that make sure we terminate it.
                self.ffmpeg.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                # We'll always end up here when there was an audio strema. Ignore any further errors.
                try:
                    self.ffmpeg.terminate()
                except Exception:
                    pass
            self.ffmpeg = None

    def outputframe(self, frame, keyframe=True, timestamp=None):
        if self.recording and self.ffmpeg:
            # Handle the case where the FFmpeg prcoess has gone away for reasons of its own.
            try:
                self.ffmpeg.stdin.write(frame)
                self.ffmpeg.stdin.flush()  # forces every frame to get timestamped individually
            except Exception as e:  # presumably a BrokenPipeError? should we check explicitly?
                self.ffmpeg = None
                
                if self.error_callback:
                    self.error_callback(e)
                else:
                    logging.warning(f"Error in ffmpeg outputframe {e}")
            else:
                self.outputtimestamp(timestamp)
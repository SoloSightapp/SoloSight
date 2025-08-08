# recorder.py
import os
import cv2
from datetime import datetime, timedelta
import threading

class CameraRecorder:
    """
    Per-camera recorder that writes frames passed to it, chunking into MP4 files.
    Use:
        r = CameraRecorder(save_dir, cam_index, chunk_minutes, max_minutes)
        r.start()  # initializes bookkeeping
        r.write_frame(frame)  # called from UI thread whenever new frame arrives
        r.stop()  # stops and flushes current writer
    """

    def __init__(self, save_dir, cam_index, chunk_minutes=5, max_minutes=60, fourcc_str='mp4v', fps=20.0):
        self.save_dir = save_dir
        self.cam_index = cam_index
        self.chunk_minutes = max(1, int(chunk_minutes))
        self.max_minutes = int(max_minutes)
        self.fourcc_str = fourcc_str
        self.fps = fps

        self.writer = None
        self.chunk_start_time = None
        self.session_start_time = None
        self.minutes_recorded = 0
        self.lock = threading.Lock()
        os.makedirs(self.save_dir, exist_ok=True)

    def _new_filename(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.save_dir, f"cam{self.cam_index}_{ts}.mp4")

    def start(self):
        with self.lock:
            self.session_start_time = datetime.now()
            self.minutes_recorded = 0
            self._start_new_chunk_if_needed(new_session=True)

    def _start_new_chunk_if_needed(self, new_session=False):
        # closes old writer if exists and opens a new one
        if self.writer:
            try:
                self.writer.release()
            except Exception:
                pass
            self.writer = None

        self.chunk_start_time = datetime.now()
        filename = self._new_filename()
        # writer will be created when first frame arrives (since width/height required)
        self.current_filename = filename
        self.writer = None  # remain None until frame with shape arrives

    def write_frame(self, frame):
        """
        frame: numpy BGR frame
        """
        if self._session_exceeded():
            # ignore further frames
            return False

        h, w = frame.shape[:2]
        with self.lock:
            if self.writer is None:
                fourcc = cv2.VideoWriter_fourcc(*self.fourcc_str)
                self.writer = cv2.VideoWriter(self.current_filename, fourcc, self.fps, (w, h))

            # write and check chunk time
            self.writer.write(frame)

            elapsed = (datetime.now() - self.chunk_start_time).total_seconds()
            if elapsed >= self.chunk_minutes * 60:
                # increment recorded minutes approx
                self.minutes_recorded += self.chunk_minutes
                if not self._session_exceeded():
                    self._start_new_chunk_if_needed()
                else:
                    # stop recording altogether
                    self.stop()
        return True

    def _session_exceeded(self):
        if self.session_start_time is None:
            return False
        elapsed_mins = (datetime.now() - self.session_start_time).total_seconds() / 60.0
        return elapsed_mins >= self.max_minutes

    def stop(self):
        with self.lock:
            if self.writer:
                try:
                    self.writer.release()
                except Exception:
                    pass
                self.writer = None
            self.session_start_time = None
            self.minutes_recorded = 0
            self.chunk_start_time = None

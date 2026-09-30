"""Video ingestion: file, webcam index or RTSP URL. Yields (frame_idx, timestamp_s, frame_bgr)."""
import time
from typing import Iterator, Optional, Tuple, Union

import cv2
import numpy as np


class VideoSource:
    def __init__(self, source: Union[str, int], realtime: bool = False, loop: bool = False,
                 target_size: Optional[Tuple[int, int]] = None):
        self.source = source
        self.realtime = realtime
        self.loop = loop
        self.target_size = target_size
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise FileNotFoundError(f"cannot open video source: {source}")
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 1 else 20.0
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    def frames(self) -> Iterator[Tuple[int, float, np.ndarray]]:
        idx = 0
        t0 = time.time()
        while True:
            ok, frame = self.cap.read()
            if not ok:
                if self.loop and isinstance(self.source, str):
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    idx = 0
                    continue
                break
            if self.target_size:
                frame = cv2.resize(frame, self.target_size)
            if self.realtime:
                wait = t0 + idx / self.fps - time.time()
                if wait > 0:
                    time.sleep(wait)
            yield idx, idx / self.fps, frame
            idx += 1

    def release(self):
        self.cap.release()

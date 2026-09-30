"""Runs the perception pipeline on a camera's video in a background thread and serves annotated MJPEG frames."""
import threading
import time
from typing import Dict, Optional

import cv2

from config import all_cameras, camera, path
from pipeline.pipeline import PerceptionPipeline
from server.services.incident_service import ingest_candidate
from server.websocket import hub


class CameraWorker:
    def __init__(self, cam_id: str):
        self.cam_id = cam_id
        self.cfg = camera(cam_id)
        self.status = "idle"
        self.jpeg: Optional[bytes] = None
        self.stats: dict = {}
        self.thread: Optional[threading.Thread] = None
        self.stop = threading.Event()
        self.video: Optional[str] = None

    def start(self, video: Optional[str] = None, realtime: bool = True):
        if self.thread and self.thread.is_alive():
            return
        self.video = str(path(video or self.cfg["demo_video"]))
        self.stop.clear()
        self.thread = threading.Thread(target=self._run, args=(realtime,), daemon=True)
        self.thread.start()

    def _run(self, realtime):
        self.status = "running"
        hub.publish({"type": "camera", "camera_id": self.cam_id, "status": self.status})
        try:
            pl = PerceptionPipeline(self.cam_id, self.video)

            def on_frame(frame, res):
                if self.stop.is_set():
                    raise StopIteration
                img = pl.annotate(frame, res)
                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 78])
                if ok:
                    self.jpeg = buf.tobytes()
                self.stats = {**res.traffic, "time_s": round(res.time_s, 1), "fps": round(pl.fps(), 1)}
                if res.frame_idx % 10 == 0:
                    hub.publish({"type": "traffic", "camera_id": self.cam_id, "stats": self.stats})

            def on_cand(c, ev):
                if c.subtype_hint == "accident" or True:
                    threading.Thread(target=ingest_candidate, daemon=True,
                                     args=(c.model_dump(), ev.directory if ev else None, self.stats)).start()

            try:
                pl.run_video(self.video, on_candidate=on_cand, on_frame=on_frame, realtime=realtime)
            except StopIteration:
                pass
            self.status = "finished"
        except Exception as e:                                # noqa
            self.status = f"error: {e}"
        hub.publish({"type": "camera", "camera_id": self.cam_id, "status": self.status})


workers: Dict[str, CameraWorker] = {c["camera_id"]: CameraWorker(c["camera_id"]) for c in all_cameras()}

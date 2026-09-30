"""Object detectors behind one interface.

- YoloDetector   : YOLOv8/YOLO11 via ultralytics (use this for REAL CCTV footage)
- ColorDetector  : hue-segmentation detector for the synthetic demo videos (no GPU, no weights)
- MotionDetector : generic fixed-camera fallback (median background subtraction)
"""
import json
import os
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

from config import cfg

HUES = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165]
COCO_NAMES = {0: "person", 2: "car", 3: "bike", 5: "truck", 7: "truck"}


@dataclass
class Detection:
    bbox: tuple          # x1,y1,x2,y2
    conf: float
    cls: str = "car"


class BaseDetector:
    name = "base"

    def detect(self, frame: np.ndarray) -> List[Detection]:
        raise NotImplementedError


def _classify(w, h, area):
    if area < 210:
        return "bike"
    return "truck" if max(w, h) >= 46 else "car"


class ColorDetector(BaseDetector):
    name = "color"

    def __init__(self):
        c = cfg("detector")["color"]
        self.min_area, self.tol, self.min_sat = c["min_area"], c["hue_tol"], c["min_sat"]
        self.min_val, self.merge_gap = c["min_val"], 22
        self.k = np.ones((3, 3), np.uint8)

    def detect(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[..., 0].astype(np.int16), hsv[..., 1], hsv[..., 2]
        base = (s >= self.min_sat) & (v >= self.min_val)
        out: List[Detection] = []
        if not base.any():
            return out
        for hue in HUES:
            d = np.abs(h - hue)
            d = np.minimum(d, 180 - d)
            m = (base & (d <= self.tol)).astype(np.uint8)
            if m.sum() < self.min_area // 2:
                continue
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, self.k)
            n, _, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
            boxes = []
            for i in range(1, n):
                x, y, w, hh, a = stats[i]
                if a >= self.min_area // 2 and w >= 4 and hh >= 4:
                    boxes.append([x - 1, y - 1, x + w + 1, y + hh + 1])
            merged = self._merge(boxes)
            for b in merged:
                w, hh = b[2] - b[0], b[3] - b[1]
                if w * hh * 0.6 < self.min_area:
                    continue
                out.append(Detection(tuple(float(c) for c in b), 0.95, _classify(w, hh, w * hh)))
        return out

    def _merge(self, boxes):
        boxes = [list(b) for b in boxes]
        changed = True
        while changed and len(boxes) > 1:
            changed = False
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    a, b = boxes[i], boxes[j]
                    dx = max(0, max(a[0] - b[2], b[0] - a[2]))
                    dy = max(0, max(a[1] - b[3], b[1] - a[3]))
                    if dx <= self.merge_gap and dy <= self.merge_gap:
                        boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                        boxes.pop(j)
                        changed = True
                        break
                if changed:
                    break
        return boxes


class MotionDetector(BaseDetector):
    name = "motion"

    def __init__(self, video_path: Optional[str] = None):
        self.c = cfg("detector")["motion"]
        self.bg = None
        if video_path:
            self.fit(video_path)

    def fit(self, video_path: str):
        cap = cv2.VideoCapture(video_path)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frames = []
        for i in np.linspace(0, max(0, n - 1), self.c["bg_samples"]).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
            ok, f = cap.read()
            if ok:
                frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
        cap.release()
        self.bg = np.median(np.stack(frames), axis=0).astype(np.uint8)

    def detect(self, frame):
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.bg is None:
            self.bg = g
        diff = cv2.absdiff(g, self.bg)
        m = (diff > self.c["diff_thresh"]).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(m)
        out = []
        for i in range(1, n):
            x, y, w, h, a = stats[i]
            if a >= self.c["min_area"]:
                out.append(Detection((float(x), float(y), float(x + w), float(y + h)), 0.8, _classify(w, h, a)))
        return out


class YoloDetector(BaseDetector):
    name = "yolo"

    def __init__(self):
        from ultralytics import YOLO  # pip install ultralytics
        c = cfg("detector")["yolo"]
        self.model = YOLO(c["weights"])
        self.conf, self.imgsz, self.classes = c["conf"], c["imgsz"], c["classes"]

    def detect(self, frame):
        res = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz, classes=self.classes, verbose=False)[0]
        out = []
        for b in res.boxes:
            x1, y1, x2, y2 = [float(t) for t in b.xyxy[0].tolist()]
            out.append(Detection((x1, y1, x2, y2), float(b.conf[0]), COCO_NAMES.get(int(b.cls[0]), "car")))
        return out


def is_synthetic(video_path: Optional[str]) -> bool:
    return bool(video_path) and os.path.exists(str(video_path) + ".json")


def build_detector(backend: Optional[str] = None, video_path: Optional[str] = None) -> BaseDetector:
    backend = backend or os.environ.get("ATOS_DETECTOR") or cfg("detector")["backend"]
    if backend == "auto":
        if is_synthetic(video_path):
            backend = "color"
        else:
            try:
                import ultralytics  # noqa: F401
                backend = "yolo"
            except Exception:
                backend = "motion"
    if backend == "color":
        return ColorDetector()
    if backend == "motion":
        return MotionDetector(video_path)
    if backend == "yolo":
        return YoloDetector()
    raise ValueError(f"unknown detector backend {backend}")

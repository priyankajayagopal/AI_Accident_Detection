"""Detector precision / recall (IoU 0.5) against synthetic ground truth + throughput."""
import time

import cv2

from config import path
from eval.common import load_meta, load_split
from pipeline.detector import build_detector
from pipeline.tracker import iou


def run(split="test", max_videos=8, backend=None):
    tp = fp = fn = 0
    n_frames, t_tot = 0, 0.0
    for r in load_split(split)[:max_videos]:
        meta = load_meta(r["video"])
        det = build_detector(backend or "color", str(path(r["video"])))
        cap = cv2.VideoCapture(str(path(r["video"])))
        for f in range(meta["n_frames"]):
            ok, frame = cap.read()
            if not ok:
                break
            t0 = time.perf_counter()
            ds = det.detect(frame)
            t_tot += time.perf_counter() - t0
            n_frames += 1
            gts = [g["bbox"] for g in meta["gt"][f] if (g["bbox"][2] - g["bbox"][0]) * (g["bbox"][3] - g["bbox"][1]) > 0]
            used = set()
            for d in ds:
                best, bi = None, 0.5
                for k, g in enumerate(gts):
                    o = iou(d.bbox, g)
                    if k not in used and o >= bi:
                        best, bi = k, o
                if best is None:
                    fp += 1
                else:
                    used.add(best); tp += 1
            fn += len(gts) - len(used)
        cap.release()
    p, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return {"detector": backend or "color", "precision": round(p, 3), "recall": round(rc, 3), "f1": round(2 * p * rc / max(1e-9, p + rc), 3),
            "detector_fps": round(n_frames / max(1e-9, t_tot), 1), "frames": n_frames}

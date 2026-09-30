"""ByteTrack-style multi-object tracker (pure numpy/scipy, no GPU).

Two-stage association like ByteTrack: (1) high-confidence detections vs all tracks,
(2) leftover tracks vs low-confidence detections. Constant-velocity prediction, IoU + centre-distance cost,
Hungarian matching. For maximum accuracy on real footage swap in `ultralytics` ByteTrack (model.track()).
"""
from dataclasses import dataclass, field
from typing import List

import numpy as np
from scipy.optimize import linear_sum_assignment

from config import cfg
from pipeline.detector import Detection


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def center(b):
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


@dataclass
class Track:
    id: int
    bbox: tuple
    cls: str
    conf: float
    hits: int = 1
    lost: int = 0
    vx: float = 0.0
    vy: float = 0.0
    confirmed: bool = False
    last_frame: int = 0

    def predicted(self):
        s = self.lost + 1
        return (self.bbox[0] + self.vx * s, self.bbox[1] + self.vy * s, self.bbox[2] + self.vx * s, self.bbox[3] + self.vy * s)


class ByteTrackLite:
    def __init__(self):
        c = cfg("tracker")
        self.high, self.iou_min = c["high_conf"], c["iou_match"]
        self.max_dist, self.max_lost, self.min_hits = c["max_center_dist_px"], c["max_lost_frames"], c["min_hits"]
        self.tracks: List[Track] = []
        self._next = 1

    def _match(self, tracks, dets, use_dist=True):
        if not tracks or not dets:
            return [], list(range(len(tracks))), list(range(len(dets)))
        cost = np.full((len(tracks), len(dets)), 1e6)
        for i, t in enumerate(tracks):
            p = t.predicted()
            pc = center(p)
            for j, d in enumerate(dets):
                o = iou(p, d.bbox)
                dc = center(d.bbox)
                dist = float(np.hypot(pc[0] - dc[0], pc[1] - dc[1]))
                if o >= self.iou_min or (use_dist and dist <= self.max_dist * 0.5):
                    cost[i, j] = 0.6 * (1 - o) + 0.4 * min(1.0, dist / self.max_dist)
        r, c = linear_sum_assignment(cost)
        matches, ut, ud = [], set(range(len(tracks))), set(range(len(dets)))
        for i, j in zip(r, c):
            if cost[i, j] < 1e5:
                matches.append((i, j)); ut.discard(i); ud.discard(j)
        return matches, sorted(ut), sorted(ud)

    def update(self, dets: List[Detection], frame_idx: int) -> List[Track]:
        high = [d for d in dets if d.conf >= self.high]
        low = [d for d in dets if d.conf < self.high]
        m1, ut, ud = self._match(self.tracks, high)
        for ti, dj in m1:
            self._apply(self.tracks[ti], high[dj], frame_idx)
        rem = [self.tracks[i] for i in ut]
        m2, ut2, _ = self._match(rem, low, use_dist=False)
        for ti, dj in m2:
            self._apply(rem[ti], low[dj], frame_idx)
        matched2 = {ti for ti, _ in m2}
        for k, t in enumerate(rem):
            if k not in matched2:
                t.lost += 1
        for j in ud:
            d = high[j]
            self.tracks.append(Track(self._next, d.bbox, d.cls, d.conf, last_frame=frame_idx))
            self._next += 1
        self.tracks = [t for t in self.tracks if t.lost <= self.max_lost]
        return [t for t in self.tracks if t.confirmed and t.lost == 0]

    def _apply(self, t: Track, d: Detection, frame_idx: int):
        oc, nc = center(t.bbox), center(d.bbox)
        dt = max(1, frame_idx - t.last_frame)
        t.vx = 0.6 * t.vx + 0.4 * (nc[0] - oc[0]) / dt
        t.vy = 0.6 * t.vy + 0.4 * (nc[1] - oc[1]) / dt
        t.bbox, t.conf, t.cls = d.bbox, d.conf, d.cls
        t.hits += 1
        t.lost = 0
        t.last_frame = frame_idx
        if t.hits >= self.min_hits:
            t.confirmed = True

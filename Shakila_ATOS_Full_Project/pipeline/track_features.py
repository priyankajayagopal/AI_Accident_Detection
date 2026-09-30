"""Per-track motion history: speed, heading, acceleration. Plus scene-level traffic analysis."""
import math
from collections import deque
from typing import Dict, List, Optional

import numpy as np

K = 6   # look-back frames used for velocity / acceleration (0.3 s at 20 fps)


class TrackFeatureStore:
    def __init__(self, fps: float, ppm: float, maxlen: int = 500):
        self.fps, self.ppm, self.maxlen = fps, ppm, maxlen
        self.hist: Dict[int, Dict[int, dict]] = {}       # tid -> frame -> state
        self.order: Dict[int, deque] = {}
        self.cls: Dict[int, str] = {}

    def update(self, frame_idx: int, tracks) -> None:
        for t in tracks:
            cx, cy = (t.bbox[0] + t.bbox[2]) / 2, (t.bbox[1] + t.bbox[3]) / 2
            h = self.hist.setdefault(t.id, {})
            o = self.order.setdefault(t.id, deque())
            self.cls[t.id] = t.cls
            st = {"cx": cx, "cy": cy, "bbox": tuple(t.bbox), "vx": 0.0, "vy": 0.0, "speed": 0.0, "acc": 0.0, "heading": None}
            prev = h.get(frame_idx - K)
            if prev is None and o:
                # use the oldest frame within K frames if the track is young
                cand = [f for f in o if frame_idx - f <= K]
                prev = h[cand[0]] if cand and cand[0] != frame_idx else None
                dtf = (frame_idx - cand[0]) if cand else 0
            else:
                dtf = K
            if prev is not None and dtf > 0:
                dt = dtf / self.fps
                vx = (cx - prev["cx"]) / dt / self.ppm
                vy = (cy - prev["cy"]) / dt / self.ppm
                st.update(vx=vx, vy=vy, speed=math.hypot(vx, vy))
                if st["speed"] > 0.4:
                    st["heading"] = math.degrees(math.atan2(vy, vx))
                pv = h.get(frame_idx - K)
                if pv is not None:
                    st["acc"] = (st["speed"] - pv["speed"]) / (K / self.fps)
            h[frame_idx] = st
            o.append(frame_idx)
            while len(o) > self.maxlen:
                h.pop(o.popleft(), None)

    def get(self, tid: int, frame_idx: int) -> Optional[dict]:
        return self.hist.get(tid, {}).get(frame_idx)

    def series(self, tid: int, key: str, f0: int, f1: int):
        h = self.hist.get(tid, {})
        return [(f, h[f][key]) for f in range(f0, f1 + 1) if f in h]

    def forget_older_than(self, frame_idx: int, keep: int = 600):
        for tid in list(self.hist):
            if not self.order[tid] or frame_idx - self.order[tid][-1] > keep:
                self.hist.pop(tid, None)
                self.order.pop(tid, None)


def traffic_state(store: TrackFeatureStore, tracks, frame_idx: int, capacity: int, slow_ms: float = 2.0) -> dict:
    """Density / speed / queue for the traffic panel."""
    speeds = []
    for t in tracks:
        s = store.get(t.id, frame_idx)
        if s is not None:
            speeds.append(s["speed"])
    n = len(tracks)
    slow = sum(1 for s in speeds if s < slow_ms)
    return {
        "vehicle_count": n,
        "density_pct": round(min(100.0, 100.0 * n / max(1, capacity)), 1),
        "avg_speed_kmh": round(float(np.mean(speeds)) * 3.6, 1) if speeds else 0.0,
        "queue_length_veh": slow,
        "frac_slow": round(slow / n, 2) if n else 0.0,
        "mean_speed_ms": float(np.mean(speeds)) if speeds else 0.0,
    }

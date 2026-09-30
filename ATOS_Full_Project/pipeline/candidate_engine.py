"""Candidate engine: turns tracks + motion features into *proposals* (never final alerts).

Six proposal signals (slide 9), each normalised to 0..1:
  overlap, proximity, closing_speed, hard_decel, trajectory_change, post_event_stationary
combined by configurable weights into one accident-confidence score. A proposal is emitted only when the score
stays above the threshold for `min_evidence_frames` (temporal evidence) AND survives a short confirmation delay
so post-event behaviour (vehicles stationary) is part of the evidence.
Also proposes single-track `stopped_vehicle` and multi-track `congestion_anomaly` events.
"""
import math
import uuid
from typing import Dict, List, Optional, Tuple

import numpy as np

from config import cfg
from pipeline.camera_geometry import CameraGeometry
from pipeline.track_features import TrackFeatureStore
from schemas.evidence import CandidateProposal


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def rect_gap_px(a, b) -> float:
    dx = max(0.0, max(a[0] - b[2], b[0] - a[2]))
    dy = max(0.0, max(a[1] - b[3], b[1] - a[3]))
    return math.hypot(dx, dy)


def overlap_ratio(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ma = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / ma if ma > 0 else 0.0


def angle_diff(a, b) -> float:
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


class CandidateEngine:
    def __init__(self, geometry: CameraGeometry, config: Optional[dict] = None):
        self.c = config or cfg("candidate_engine")
        self.g = geometry
        self.fps, self.ppm = geometry.fps, geometry.ppm
        self.win = int(self.c["window_s"] * self.fps)
        self.confirm = int(1.5 * self.fps)
        self.pair_state: Dict[Tuple[int, int], dict] = {}
        self.emitted: List[dict] = []          # {frame, centroid, ids}
        self.single_state: Dict[int, dict] = {}
        self.cong_last = -10 ** 9
        self.w = self.c["weights"]

    # ------------------------------------------------------------------ pair signals
    def pair_signals(self, a: int, b: int, f: int, store: TrackFeatureStore) -> Optional[Tuple[dict, dict]]:
        ha, hb = store.hist.get(a, {}), store.hist.get(b, {})
        frames = [x for x in range(f - self.win, f + 1) if x in ha and x in hb]
        if len(frames) < 3:
            return None
        gaps = [(rect_gap_px(ha[x]["bbox"], hb[x]["bbox"]), x) for x in frames]
        min_gap_px, min_f = min(gaps)
        contact_px = self.c["contact_gap_m"] * self.ppm
        if min_gap_px > contact_px:
            return None
        ov = max(overlap_ratio(ha[x]["bbox"], hb[x]["bbox"]) for x in frames)
        touch = [x for (g, x) in gaps if g <= 0.3 * self.ppm]
        e = touch[0] if touch else min_f                       # event frame
        # closing (relative) speed just before the event
        fb = max(frames[0], e - 4)
        sa, sb = ha.get(fb) or ha[frames[0]], hb.get(fb) or hb[frames[0]]
        rel = math.hypot(sa["vx"] - sb["vx"], sa["vy"] - sb["vy"])
        speed_before = max(sa["speed"], sb["speed"])
        # peak deceleration of either vehicle (from the event window onwards)
        dec = 0.0
        for x in frames:
            if x >= e - 3:
                dec = max(dec, -ha[x]["acc"], -hb[x]["acc"])
        # trajectory change: heading before vs after event, for each vehicle
        hc = 0.0
        for h in (ha, hb):
            pre = [h[x]["heading"] for x in range(e - 10, e - 2) if x in h and h[x]["heading"] is not None]
            post = [h[x]["heading"] for x in range(e + 1, min(f, e + 14) + 1) if x in h and h[x]["heading"] is not None]
            if pre and post:
                hc = max(hc, angle_diff(float(np.median(pre)), float(np.median(post))))
        # post-event stationary duration (both vehicles) counted back from now
        st_n = 0
        for x in range(f, e - 1, -1):
            if x in ha and x in hb and ha[x]["speed"] < self.c["stationary_speed_ms"] and hb[x]["speed"] < self.c["stationary_speed_ms"]:
                st_n += 1
            else:
                break
        st_s = st_n / self.fps
        min_gap_m = min_gap_px / self.ppm
        sig = {
            "overlap": _clip(ov / self.c["overlap_full"]),
            "proximity": _clip(1 - min_gap_m / self.c["contact_gap_m"]),
            "closing_speed": _clip(rel / self.c["closing_speed_full_ms"]),
            "hard_decel": _clip((dec - self.c["decel_low_ms2"]) / (self.c["decel_full_ms2"] - self.c["decel_low_ms2"])),
            "trajectory_change": _clip(hc / self.c["heading_change_full_deg"]),
            "post_event_stationary": _clip(st_s / self.c["stationary_full_s"]),
        }
        raw = {"max_overlap": ov, "min_gap_m": min_gap_m, "closing_speed_ms": rel, "peak_decel_ms2": dec,
               "max_heading_change_deg": hc, "stationary_s": st_s, "speed_before_ms": speed_before,
               "event_frame": e}
        return sig, raw

    def score(self, sig: dict) -> float:
        return float(sum(self.w[k] * v for k, v in sig.items()))

    # ------------------------------------------------------------------ helpers
    def _scene(self, tracks, store, f, cx, cy):
        speeds, near = [], 0
        for t in tracks:
            s = store.get(t.id, f)
            if s:
                speeds.append(s["speed"])
                if math.hypot(s["cx"] - cx, s["cy"] - cy) < 200:
                    near += 1
        n = max(1, len(speeds))
        return {"local_tracks": near, "mean_speed_all_ms": float(np.mean(speeds)) if speeds else 0.0,
                "frac_slow_tracks": sum(1 for s in speeds if s < 2.0) / n}

    def _suppressed(self, f, cx, cy, ids=()):
        for e in self.emitted:
            if f - e["frame"] < 60 * self.fps and (math.hypot(cx - e["c"][0], cy - e["c"][1]) < self.c["zone_suppress_m"] * self.ppm
                                                    or set(ids) & set(e["ids"])):
                return True
        return False

    def _mk(self, camera_id, f, e, subtype, ids, score, sig, raw, tracks, store, scene, evid):
        by = {t.id: t for t in tracks}
        bboxes = {i: [float(v) for v in by[i].bbox] for i in ids if i in by}
        cx = float(np.mean([(b[0] + b[2]) / 2 for b in bboxes.values()])) if bboxes else 0.0
        cy = float(np.mean([(b[1] + b[3]) / 2 for b in bboxes.values()])) if bboxes else 0.0
        feats = {"max_overlap": raw.get("max_overlap", 0.0), "min_gap_m": raw.get("min_gap_m", 99.0),
                 "closing_speed_ms": raw.get("closing_speed_ms", 0.0), "peak_decel_ms2": raw.get("peak_decel_ms2", 0.0),
                 "max_heading_change_deg": raw.get("max_heading_change_deg", 0.0), "stationary_s": raw.get("stationary_s", 0.0),
                 "n_tracks": float(len(ids)), "speed_before_ms": raw.get("speed_before_ms", 0.0),
                 "speed_after_ms": float(np.mean([(store.get(i, f) or {"speed": 0})["speed"] for i in ids])) if ids else 0.0,
                 "evidence_frames": float(evid), "local_tracks": float(scene["local_tracks"]),
                 "mean_speed_all_ms": scene["mean_speed_all_ms"], "frac_slow_tracks": scene["frac_slow_tracks"],
                 "score": float(score)}
        self.emitted.append({"frame": f, "c": (cx, cy), "ids": list(ids)})
        return CandidateProposal(candidate_id=uuid.uuid4().hex[:8], camera_id=camera_id, frame_idx=f,
                                 event_frame_idx=int(e), video_time_s=f / self.fps, subtype_hint=subtype,
                                 track_ids=list(ids), score=float(score), signals={k: float(v) for k, v in sig.items()},
                                 features=feats, bboxes=bboxes, vehicle_types=[store.cls.get(i, "car") for i in ids],
                                 centroid_px=[cx, cy])

    # ------------------------------------------------------------------ main
    def update(self, f: int, tracks, store: TrackFeatureStore) -> List[CandidateProposal]:
        out: List[CandidateProposal] = []
        cam = self.g.camera_id
        ids = [t.id for t in tracks]
        thr, need = self.c["propose_threshold"], self.c["min_evidence_frames"]
        centers = {t.id: ((t.bbox[0] + t.bbox[2]) / 2, (t.bbox[1] + t.bbox[3]) / 2) for t in tracks}
        live_pairs = set()
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                ca, cb = centers[a], centers[b]
                if math.hypot(ca[0] - cb[0], ca[1] - cb[1]) > 260:
                    continue
                r = self.pair_signals(a, b, f, store)
                if r is None:
                    continue
                sig, raw = r
                sc = self.score(sig)
                key = (a, b)
                live_pairs.add(key)
                ps = self.pair_state.setdefault(key, {"consec": 0, "first": None, "done": False})
                if ps["done"]:
                    continue
                if sc >= thr:
                    ps["consec"] += 1
                    if ps["consec"] == 1:
                        ps["first"] = f
                else:
                    ps["consec"], ps["first"] = 0, None
                    continue
                if ps["consec"] >= need and f - ps["first"] >= self.confirm:
                    cx, cy = (ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2
                    if self._suppressed(f, cx, cy, (a, b)):
                        ps["done"] = True
                        continue
                    sub = "accident" if raw["max_overlap"] > 0.02 else "near_miss"
                    scene = self._scene(tracks, store, f, cx, cy)
                    out.append(self._mk(cam, f, raw["event_frame"], sub, [a, b], sc, sig, raw, tracks, store, scene, ps["consec"]))
                    ps["done"] = True
        for k in list(self.pair_state):
            if k not in live_pairs and not self.pair_state[k]["done"]:
                self.pair_state.pop(k)
        out += self._single_track(f, tracks, store)
        out += self._congestion(f, tracks, store)
        if len(store.hist) > 200:
            store.forget_older_than(f)
        return out

    # single stopped vehicle -----------------------------------------------------
    def _single_track(self, f, tracks, store):
        sc = self.c["single_track"]
        res = []
        stat_thr = 0.5
        for t in tracks:
            h = store.hist.get(t.id, {})
            s = h.get(f)
            if not s:
                continue
            st = self.single_state.setdefault(t.id, {"stopped_since": None, "done": False, "max_prior": 0.0, "dir": None})
            if s["speed"] > 1.5 and s["heading"] is not None:
                st["dir"] = s["heading"]
            if s["speed"] >= stat_thr:
                st["stopped_since"] = None
                st["max_prior"] = max(st["max_prior"], s["speed"])
                continue
            if st["stopped_since"] is None:
                st["stopped_since"] = f
            dur = (f - st["stopped_since"]) / self.fps
            if st["done"] or dur < sc["stopped_after_moving_s"] or st["max_prior"] < sc["prior_speed_ms"]:
                continue
            # in a queue? another slow vehicle within radius, AHEAD of us
            in_queue = False
            for o in tracks:
                if o.id == t.id:
                    continue
                so = store.get(o.id, f)
                if not so or so["speed"] > 2.0:
                    continue
                dx, dy = so["cx"] - s["cx"], so["cy"] - s["cy"]
                dist = math.hypot(dx, dy)
                if dist < sc["queue_radius_m"] * self.ppm:
                    if st["dir"] is None or angle_diff(math.degrees(math.atan2(dy, dx)), st["dir"]) < 60:
                        in_queue = True
                        break
            if in_queue:
                continue
            if self._suppressed(f, s["cx"], s["cy"], (t.id,)):
                st["done"] = True
                continue
            prior_dec = max([-x["acc"] for x in h.values() if x["acc"] < 0] or [0.0])
            raw = {"stationary_s": dur, "speed_before_ms": st["max_prior"], "peak_decel_ms2": prior_dec}
            scene = self._scene(tracks, store, f, s["cx"], s["cy"])
            sig = {k: 0.0 for k in self.w}
            sig["post_event_stationary"] = _clip(dur / 8.0)
            res.append(self._mk(self.g.camera_id, f, st["stopped_since"], "stopped_vehicle", [t.id],
                                _clip(dur / 8.0), sig, raw, tracks, store, scene, int(dur * self.fps)))
            st["done"] = True
        return res

    # congestion anomaly ---------------------------------------------------------
    def _congestion(self, f, tracks, store):
        cc = self.c["congestion"]
        slow = [t for t in tracks if (store.get(t.id, f) or {"speed": 9})["speed"] < cc["slow_speed_ms"]]
        st = self.single_state.setdefault(-1, {"since": None})
        if len(slow) >= cc["min_tracks"]:
            if st["since"] is None:
                st["since"] = f
            if (f - st["since"]) / self.fps >= cc["min_duration_s"] and f - self.cong_last > 60 * self.fps:
                self.cong_last = f
                ids = [t.id for t in slow][:12]
                cx = float(np.mean([centers_x(store, i, f) for i in ids])); cy = float(np.mean([centers_y(store, i, f) for i in ids]))
                scene = self._scene(tracks, store, f, cx, cy)
                sig = {k: 0.0 for k in self.w}
                sig["proximity"] = 0.5
                raw = {"stationary_s": (f - st["since"]) / self.fps, "speed_before_ms": 0.0}
                return [self._mk(self.g.camera_id, f, st["since"], "congestion_anomaly", ids, 0.35, sig, raw, tracks, store, scene, f - st["since"])]
        else:
            st["since"] = None
        return []


def centers_x(store, tid, f):
    s = store.get(tid, f)
    return s["cx"] if s else 0.0


def centers_y(store, tid, f):
    s = store.get(tid, f)
    return s["cy"] if s else 0.0

"""Synthetic candidate payloads (no video) for unit tests, fault-injection and agent evaluation."""
import random
import uuid
from typing import Tuple


def synthetic_candidate(kind: str = "accident", seed: int = 0) -> Tuple[dict, dict]:
    r = random.Random(seed)
    acc = kind == "accident"
    sig = {"overlap": 1.0, "proximity": 1.0, "closing_speed": 1.0, "hard_decel": 0.9, "trajectory_change": 0.4,
           "post_event_stationary": 0.8} if acc else {"overlap": 0.0, "proximity": 0.4, "closing_speed": 0.5, "hard_decel": 0.5,
                                                       "trajectory_change": 0.0, "post_event_stationary": 0.0}
    feats = {"max_overlap": 0.3 if acc else 0.0, "min_gap_m": 0.0 if acc else 0.8, "closing_speed_ms": 15.0 + r.random() if acc else 6.0,
             "peak_decel_ms2": 30.0 if acc else 6.0, "max_heading_change_deg": 25.0 if acc else 2.0, "stationary_s": 1.5 if acc else 0.0,
             "n_tracks": 2.0, "speed_before_ms": 12.0 if acc else 9.0, "speed_after_ms": 0.2 if acc else 5.0, "evidence_frames": 30.0,
             "local_tracks": 4.0, "mean_speed_all_ms": 5.0, "frac_slow_tracks": 0.2, "score": 0.78 if acc else 0.42}
    cand = {"candidate_id": uuid.uuid4().hex[:8], "camera_id": "CAM001", "frame_idx": 172, "event_frame_idx": 140, "video_time_s": 8.6,
            "subtype_hint": "accident" if acc else "near_miss", "track_ids": [10, 13], "score": feats["score"], "signals": sig,
            "features": feats, "bboxes": {10: [290, 185, 326, 203], 13: [297, 170, 315, 206]}, "vehicle_types": ["car", "car"],
            "centroid_px": [308, 190]}
    traffic = {"vehicle_count": 9, "density_pct": 64.0, "avg_speed_kmh": 14.0, "queue_length_veh": 4, "frac_slow": 0.4}
    return cand, traffic

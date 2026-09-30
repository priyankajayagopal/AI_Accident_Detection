from typing import Dict
from pydantic import BaseModel, Field

FEATURE_NAMES = [
    "max_overlap", "min_gap_m", "closing_speed_ms", "peak_decel_ms2", "max_heading_change_deg",
    "stationary_s", "n_tracks", "speed_before_ms", "speed_after_ms", "evidence_frames",
    "local_tracks", "mean_speed_all_ms", "frac_slow_tracks", "score",
]
CLASSES = ["accident", "near_miss", "stopped_vehicle", "congestion_anomaly", "no_incident"]


class ClassifierResult(BaseModel):
    predicted: str
    accident_prob: float = Field(ge=0, le=1)
    probs: Dict[str, float]
    model_version: str = "classifier_v1"
    used_fallback: bool = False

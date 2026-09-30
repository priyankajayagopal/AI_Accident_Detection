"""Candidate proposal emitted by the CV pipeline + evidence bundle."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CandidateProposal(BaseModel):
    candidate_id: str
    camera_id: str
    frame_idx: int
    event_frame_idx: int
    video_time_s: float
    subtype_hint: str = "accident"          # accident | stopped_vehicle | congestion_anomaly | near_miss
    track_ids: List[int]
    score: float
    signals: Dict[str, float]               # the 6 normalised signals (0..1)
    features: Dict[str, float]              # raw features for the classifier
    bboxes: Dict[int, List[float]] = Field(default_factory=dict)   # track_id -> [x1,y1,x2,y2] at emission
    vehicle_types: List[str] = Field(default_factory=list)
    centroid_px: List[float] = Field(default_factory=lambda: [0.0, 0.0])


class EvidenceBundle(BaseModel):
    directory: str
    keyframes: Dict[str, str] = Field(default_factory=dict)   # before / impact / after
    clip: Optional[str] = None
    trajectory_plot: Optional[str] = None
    features_json: Optional[str] = None

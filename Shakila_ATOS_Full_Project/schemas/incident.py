"""Core data contract: the single source of truth for an incident (DB, API, agents, dashboard)."""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentStatus(str, Enum):
    PROPOSED = "proposed"
    UNDER_VERIFICATION = "under_verification"
    VERIFIED = "verified"
    OPERATOR_APPROVED = "operator_approved"
    DISPATCH_RECOMMENDED = "dispatch_recommended"
    SIMULATED = "simulated"
    CLOSED = "closed"
    REJECTED = "rejected"


class IncidentSubtype(str, Enum):
    ACCIDENT = "accident"
    NEAR_MISS = "near_miss"
    STOPPED_VEHICLE = "stopped_vehicle"
    CONGESTION_ANOMALY = "congestion_anomaly"
    UNKNOWN = "unknown"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class UncertaintyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IncidentLocation(BaseModel):
    camera_id: str
    road_segment: Optional[str] = None
    junction_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_uncertainty: UncertaintyLevel = UncertaintyLevel.HIGH


class EstimatedSeverity(BaseModel):
    level: SeverityLevel = SeverityLevel.UNKNOWN
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    uncertainty: UncertaintyLevel = UncertaintyLevel.HIGH
    reasons: List[str] = Field(default_factory=list)


class IncidentRecord(BaseModel):
    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: IncidentStatus = IncidentStatus.PROPOSED
    subtype: IncidentSubtype = IncidentSubtype.UNKNOWN

    # probabilities & scores
    proposal_score: Optional[float] = None
    classifier_confidence: Optional[float] = None
    vlm_confidence: Optional[float] = None

    # human-in-the-loop
    requires_human_approval: bool = True
    human_approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # severity & location
    estimated_severity: EstimatedSeverity = Field(default_factory=EstimatedSeverity)
    location: IncidentLocation

    # scene facts (from CV)
    vehicles_involved: int = 0
    vehicle_types: List[str] = Field(default_factory=list)
    people_involved: int = 0
    blocked_lanes: int = 0
    traffic_density_pct: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    queue_length_veh: Optional[int] = None
    impact_speed_kmh: Optional[float] = None
    signals: Dict[str, float] = Field(default_factory=dict)

    # outputs of the agent workflow (validated dicts, see schemas/agent_outputs.py)
    verification: Optional[Dict[str, Any]] = None
    dispatch: Optional[Dict[str, Any]] = None
    clearance: Optional[Dict[str, Any]] = None
    simulation: Optional[Dict[str, Any]] = None
    report_path: Optional[str] = None
    rejection_reason: Optional[str] = None
    flags: List[str] = Field(default_factory=list)

    # evidence & audit
    evidence_paths: List[str] = Field(default_factory=list)
    evidence_dir: Optional[str] = None
    frame_idx: Optional[int] = None
    detected_at_video_s: Optional[float] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

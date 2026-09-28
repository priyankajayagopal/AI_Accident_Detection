from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime
import uuid

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
    MINOR = "minor"
    MODERATE = "moderate"
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
    reasons: List[str] = []

class IncidentRecord(BaseModel):
    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: IncidentStatus = IncidentStatus.PROPOSED
    subtype: IncidentSubtype = IncidentSubtype.UNKNOWN
    
    # Probabilities & Scores
    proposal_score: Optional[float] = None
    classifier_confidence: Optional[float] = None
    vlm_confidence: Optional[float] = None
    
    # Human-in-the-loop fields
    requires_human_approval: bool = True
    human_approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # Severity & Location
    estimated_severity: EstimatedSeverity = EstimatedSeverity()
    location: IncidentLocation
    
    # Evidence & Audit
    evidence_paths: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
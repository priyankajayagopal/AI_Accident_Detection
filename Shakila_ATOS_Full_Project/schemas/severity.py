from typing import Dict, List
from pydantic import BaseModel, Field

SEVERITY_FEATURES = ["collision_intensity", "vehicle_count", "heavy_vehicle", "people_involved",
                     "blocked_lane_ratio", "blocked_lanes", "impact_speed_kmh", "traffic_density_pct", "queue_length"]


class SeverityFeatures(BaseModel):
    collision_intensity: float = 0.0      # peak decel (m/s^2)
    vehicle_count: int = 1
    heavy_vehicle: int = 0                # 1 if a truck/bus is involved
    people_involved: int = 0
    blocked_lane_ratio: float = 0.0       # worst blocked share within one direction group (1.0 = full blockage)
    blocked_lanes: int = 0
    impact_speed_kmh: float = 0.0
    traffic_density_pct: float = 0.0
    queue_length: int = 0


class SeverityResult(BaseModel):
    level: str
    confidence: float = Field(ge=0, le=1)
    probs: Dict[str, float] = {}
    reasons: List[str] = []
    used_fallback: bool = False

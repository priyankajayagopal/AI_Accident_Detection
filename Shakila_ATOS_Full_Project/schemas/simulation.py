from typing import Dict, List
from pydantic import BaseModel


class ScenarioMetrics(BaseModel):
    emergency_arrival_s: float
    queue_dissipation_s: float
    avg_delay_s: float
    recovery_s: float
    max_queue_veh: float
    vehicles_completed: float


class SimulationResult(BaseModel):
    engine: str
    seeds: int
    baseline: ScenarioMetrics
    treatment: ScenarioMetrics
    improvement_pct: Dict[str, float]
    queue_series: Dict[str, List[float]] = {}     # 'baseline' / 'treatment' / 't' (downsampled)
    notes: str = ""

"""Pydantic contracts for every agent output. The guardrail rejects anything that does not validate."""
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Service = Literal["ambulance", "police", "fire", "tow"]


class VerifierOutput(BaseModel):
    decision: Literal["verified", "rejected", "needs_review"]
    confidence: float = Field(ge=0, le=1)
    combined_score: float = Field(ge=0, le=1)
    subtype: str
    reasons: List[str] = Field(min_length=1)
    used_fallbacks: List[str] = []


class SeverityOutput(BaseModel):
    level: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0, le=1)
    reasons: List[str] = Field(min_length=1)
    blocked_lanes: int = Field(ge=0)
    used_fallbacks: List[str] = []


class DispatchPlan(BaseModel):
    services: List[Service] = Field(min_length=1)
    priority: Literal["P1", "P2", "P3", "P4"]
    eta_s: Dict[str, float] = {}
    rationale: str
    advisory_only: bool = True
    used_fallbacks: List[str] = []


class SignalAction(BaseModel):
    junction: str
    action: Literal["hold_red_main", "extend_green_main", "emergency_preempt", "normal"]
    seconds: float = Field(ge=0)


class ClearancePlan(BaseModel):
    diversion_route: List[str]             # node ids for Route B
    diversion_eta_s: float
    emergency_route: List[str]             # node ids station -> incident
    emergency_eta_s: float
    blocked_edge: str
    signal_actions: List[SignalAction]
    strategy: str
    actuation: Literal["simulation_only"] = "simulation_only"
    used_fallbacks: List[str] = []


class GuardrailResult(BaseModel):
    passed: bool
    violations: List[str] = []
    warnings: List[str] = []
    checked: str = ""


class AgentTraceEntry(BaseModel):
    agent: str
    step: str
    tools: List[str] = []
    decision: str = ""
    detail: Optional[dict] = None
    latency_ms: float = 0.0
    ts: str = ""

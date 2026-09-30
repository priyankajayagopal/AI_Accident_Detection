"""Shared state passed through the agent graph. One AgentContext per incident run."""
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from schemas.agent_outputs import AgentTraceEntry
from schemas.incident import IncidentRecord


@dataclass
class AgentContext:
    store: Any
    incident: IncidentRecord
    candidate: Dict[str, Any] = field(default_factory=dict)
    traffic: Dict[str, Any] = field(default_factory=dict)
    evidence_dir: Optional[str] = None
    faults: Set[str] = field(default_factory=set)          # fault injection for evaluation
    publisher: Optional[Callable[[dict], None]] = None
    llm: Any = None
    halted: bool = False
    outputs: Dict[str, Any] = field(default_factory=dict)
    trace: List[AgentTraceEntry] = field(default_factory=list)
    fallbacks_used: List[str] = field(default_factory=list)
    seeds: Optional[List[int]] = None

    def log(self, agent: str, step: str, tools=None, decision: str = "", detail: dict = None, t0: float = None):
        e = AgentTraceEntry(agent=agent, step=step, tools=tools or [], decision=decision, detail=detail,
                            latency_ms=round((time.perf_counter() - t0) * 1000, 1) if t0 else 0.0,
                            ts=datetime.now(timezone.utc).isoformat())
        self.trace.append(e)
        self.store.add_trace(self.incident.incident_id, e.model_dump())
        if self.publisher:
            self.publisher({"type": "agent_step", "incident_id": self.incident.incident_id, "entry": e.model_dump()})

    def alert(self, level: str, message: str):
        self.store.add_alert(self.incident.incident_id, level, message)
        if self.publisher:
            self.publisher({"type": "alert", "incident_id": self.incident.incident_id, "level": level, "message": message})

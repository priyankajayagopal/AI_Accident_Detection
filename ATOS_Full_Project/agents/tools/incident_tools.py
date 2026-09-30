"""Incident persistence interface + state-transition helper. The DB store lives in server/repositories.py."""
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from safety import audit_logger
from safety.state_machine import transition_state
from schemas.incident import IncidentLocation, IncidentRecord, IncidentStatus, UncertaintyLevel, utcnow


class IncidentStore:
    def get(self, iid: str) -> IncidentRecord: raise NotImplementedError
    def save(self, inc: IncidentRecord) -> None: raise NotImplementedError
    def list(self, limit: int = 100) -> List[IncidentRecord]: raise NotImplementedError
    def add_event(self, iid, actor, from_status, to_status, note) -> None: raise NotImplementedError
    def add_trace(self, iid: str, entry: dict) -> None: raise NotImplementedError
    def add_alert(self, iid: str, level: str, message: str) -> None: raise NotImplementedError
    def set_payload(self, iid: str, payload: dict) -> None: raise NotImplementedError
    def get_payload(self, iid: str) -> dict: raise NotImplementedError
    def traces(self, iid: str) -> List[dict]: raise NotImplementedError
    def events(self, iid: str) -> List[dict]: raise NotImplementedError


class MemoryStore(IncidentStore):
    """Thread-safe in-memory store for scripts, tests and evaluation."""

    def __init__(self):
        self._i: Dict[str, IncidentRecord] = {}
        self._payload: Dict[str, dict] = {}
        self._traces: Dict[str, List[dict]] = {}
        self._events: Dict[str, List[dict]] = {}
        self._alerts: List[dict] = []
        self._lock = threading.RLock()

    def get(self, iid):
        with self._lock:
            return self._i[iid].model_copy(deep=True)

    def save(self, inc):
        with self._lock:
            self._i[inc.incident_id] = inc.model_copy(deep=True)

    def list(self, limit=100):
        with self._lock:
            return sorted(self._i.values(), key=lambda x: x.created_at, reverse=True)[:limit]

    def add_event(self, iid, actor, from_status, to_status, note):
        self._events.setdefault(iid, []).append({"ts": utcnow().isoformat(), "actor": actor, "from": from_status,
                                                 "to": to_status, "note": note})

    def add_trace(self, iid, entry):
        self._traces.setdefault(iid, []).append(entry)

    def add_alert(self, iid, level, message):
        self._alerts.append({"incident_id": iid, "level": level, "message": message, "ts": utcnow().isoformat()})

    def set_payload(self, iid, payload):
        self._payload[iid] = payload

    def get_payload(self, iid):
        return self._payload.get(iid, {})

    def traces(self, iid):
        return list(self._traces.get(iid, []))

    def events(self, iid):
        return list(self._events.get(iid, []))


def apply_transition(store: IncidentStore, inc: IncidentRecord, nxt: IncidentStatus, actor: str, note: str = "",
                     publisher: Optional[Callable] = None) -> IncidentRecord:
    """The ONLY place status changes. Validates via the state machine, audits, persists, publishes."""
    prev = inc.status
    transition_state(prev, nxt, actor, note)               # raises on illegal / unauthorised transition
    inc.status = nxt
    inc.updated_at = utcnow()
    if nxt == IncidentStatus.OPERATOR_APPROVED:
        inc.human_approved, inc.approved_by, inc.approved_at = True, actor.split(":", 1)[-1], inc.updated_at
    store.save(inc)
    store.add_event(inc.incident_id, actor, prev.value if prev else None, nxt.value, note)
    audit_logger.log_event("transition", inc.incident_id, actor, {"from": prev.value if prev else None, "to": nxt.value, "note": note})
    if publisher:
        publisher({"type": "incident_updated", "incident_id": inc.incident_id, "status": nxt.value})
    return inc


def create_incident_from_candidate(store: IncidentStore, candidate: dict, camera: dict, evidence_dir: Optional[str],
                                   traffic: Optional[dict] = None, publisher: Optional[Callable] = None) -> IncidentRecord:
    loc = IncidentLocation(camera_id=candidate["camera_id"], road_segment=camera.get("road_segment"),
                           junction_id=camera.get("junction_id"), latitude=camera.get("latitude"),
                           longitude=camera.get("longitude"), location_uncertainty=UncertaintyLevel.MEDIUM)
    inc = IncidentRecord(location=loc, proposal_score=candidate.get("score"), signals=candidate.get("signals", {}),
                         evidence_dir=evidence_dir, frame_idx=candidate.get("frame_idx"),
                         detected_at_video_s=candidate.get("video_time_s"),
                         evidence_paths=_evidence_files(evidence_dir))
    inc.status = None  # type: ignore  (first transition None -> PROPOSED)
    transition_state(None, IncidentStatus.PROPOSED, "pipeline/candidate_engine")
    inc.status = IncidentStatus.PROPOSED
    store.save(inc)
    store.set_payload(inc.incident_id, {"candidate": candidate, "traffic": traffic or {}, "evidence_dir": evidence_dir})
    store.add_event(inc.incident_id, "pipeline/candidate_engine", None, "proposed", f"score={candidate.get('score', 0):.2f}")
    audit_logger.log_event("transition", inc.incident_id, "pipeline/candidate_engine", {"from": None, "to": "proposed"})
    if publisher:
        publisher({"type": "incident_created", "incident_id": inc.incident_id})
    return inc


def _evidence_files(d: Optional[str]) -> List[str]:
    if not d:
        return []
    from pathlib import Path
    p = Path(d)
    return sorted(str(x) for x in p.glob("*") if x.suffix in (".jpg", ".png", ".mp4", ".json") and "_raw" not in x.name) if p.exists() else []

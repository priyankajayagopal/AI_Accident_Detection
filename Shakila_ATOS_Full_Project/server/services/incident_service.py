from typing import Optional

from agents.tools.incident_tools import create_incident_from_candidate
from config import camera
from server.dependencies import get_orchestrator, get_store
from server.websocket import hub
from workers.proposal_logger import log_proposal
from schemas.evidence import CandidateProposal


def ingest_candidate(candidate: dict, evidence_dir: Optional[str], traffic: Optional[dict] = None, faults=None) -> str:
    """Pipeline -> DB -> verification phase. Runs in a worker thread."""
    store, orch = get_store(), get_orchestrator()
    try:
        log_proposal(CandidateProposal(**candidate))
    except Exception:
        pass
    inc = create_incident_from_candidate(store, candidate, camera(candidate["camera_id"]), evidence_dir, traffic, hub.publish)
    orch.verification_phase(inc.incident_id, set(faults or ()))
    return inc.incident_id

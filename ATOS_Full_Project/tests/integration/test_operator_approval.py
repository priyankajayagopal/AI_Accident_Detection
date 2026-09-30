import pytest
from agents.orchestrator import Orchestrator
from agents.tools.incident_tools import MemoryStore, create_incident_from_candidate
from config import camera
from safety.state_machine import InvalidTransitionError
from tests.synthetic.synthetic_incidents import synthetic_candidate


def test_reject_then_close_and_no_reapprove():
    store = MemoryStore(); o = Orchestrator(store, engine="simple")
    c, t = synthetic_candidate("accident")
    inc = create_incident_from_candidate(store, c, camera("CAM001"), None, t)
    o.verification_phase(inc.incident_id)
    o.reject(inc.incident_id, "operator1", "false alarm")
    with pytest.raises(InvalidTransitionError):
        o.approve(inc.incident_id, "operator1")
    o.close(inc.incident_id, "operator1")

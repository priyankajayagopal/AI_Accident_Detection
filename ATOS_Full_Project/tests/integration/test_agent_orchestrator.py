import pytest
from agents.orchestrator import Orchestrator
from agents.tools.incident_tools import MemoryStore, create_incident_from_candidate
from config import camera
from safety.state_machine import InvalidTransitionError
from tests.synthetic.synthetic_incidents import synthetic_candidate


def _setup(kind="accident", **kw):
    store = MemoryStore()
    o = Orchestrator(store, engine=kw.get("engine", "simple"))
    c, t = synthetic_candidate(kind)
    inc = create_incident_from_candidate(store, c, camera("CAM001"), None, t)
    return store, o, inc


def test_full_lifecycle_with_human_gate():
    store, o, inc = _setup()
    inc = o.verification_phase(inc.incident_id)
    assert inc.status.value == "verified"
    with pytest.raises(PermissionError):
        o.response_phase(inc.incident_id)            # cannot respond before approval
    o.approve(inc.incident_id, "operator1")
    inc = o.response_phase(inc.incident_id, seeds=[1])
    assert inc.status.value == "simulated" and inc.dispatch and inc.clearance and inc.simulation and inc.report_path
    o.close(inc.incident_id, "operator1")
    assert store.get(inc.incident_id).status.value == "closed"


def test_langgraph_engine_matches_simple():
    for eng in ("simple", "langgraph"):
        store, o, inc = _setup(engine=eng)
        assert o.verification_phase(inc.incident_id).status.value == "verified"


@pytest.mark.parametrize("fault", ["vlm_down", "classifier_missing", "severity_missing", "dispatcher_error", "routing_error", "report_error"])
def test_fallbacks_keep_system_running(fault):
    store, o, inc = _setup()
    o.verification_phase(inc.incident_id, {fault})
    o.approve(inc.incident_id, "operator1")
    inc = o.response_phase(inc.incident_id, {fault}, seeds=[1])
    assert inc.status.value == "simulated"


def test_non_accident_is_not_sent_to_operator():
    store, o, inc = _setup("near_miss")
    inc = o.verification_phase(inc.incident_id)
    assert inc.status.value == "rejected"

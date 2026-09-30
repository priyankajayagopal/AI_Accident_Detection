"""Agent-system evaluation: task success, tool-call accuracy, consistency, and robustness under injected faults."""
import itertools

from agents.orchestrator import Orchestrator
from agents.tools.incident_tools import MemoryStore, create_incident_from_candidate
from config import camera
from tests.synthetic.synthetic_incidents import synthetic_candidate

EXPECTED = ["verifier_agent", "severity_agent", "dispatcher_agent", "traffic_clearance_agent", "reporting_agent"]
FAULT_SETS = [set(), {"vlm_down"}, {"classifier_missing"}, {"severity_missing"}, {"dispatcher_error"}, {"routing_error"},
              {"report_error"}, {"vlm_invalid", "severity_missing"}, {"vlm_down", "classifier_missing", "severity_missing"}]


def _lifecycle(seed, faults):
    store = MemoryStore()
    orch = Orchestrator(store, engine="simple")
    cand, tr = synthetic_candidate("accident", seed)
    inc = create_incident_from_candidate(store, cand, camera("CAM001"), None, tr)
    orch.verification_phase(inc.incident_id, faults)
    cur = store.get(inc.incident_id)
    if cur.status.value != "verified":
        return store, cur, False
    orch.approve(inc.incident_id, "operator1")
    cur = orch.response_phase(inc.incident_id, faults, seeds=[1])
    return store, cur, cur.status.value == "simulated" and bool(cur.report_path)


def run(n_per_fault=3):
    total = ok = tool_ok = 0
    per_fault = {}
    for faults in FAULT_SETS:
        s = 0
        for seed in range(n_per_fault):
            store, inc, success = _lifecycle(seed, faults)
            agents = {t["agent"] for t in store.traces(inc.incident_id)}
            tool_ok += all(a in agents for a in EXPECTED)
            total += 1; ok += success; s += success
        per_fault["+".join(sorted(faults)) or "no_fault"] = f"{s}/{n_per_fault}"
    # consistency: same input twice -> same decisions
    a = _lifecycle(1, set())[1]; b = _lifecycle(1, set())[1]
    consistent = (a.estimated_severity.level == b.estimated_severity.level and (a.dispatch or {}).get("services") == (b.dispatch or {}).get("services")
                  and (a.clearance or {}).get("diversion_route") == (b.clearance or {}).get("diversion_route"))
    return {"runs": total, "task_success_rate": round(ok / total, 3), "tool_call_accuracy": round(tool_ok / total, 3),
            "consistency": consistent, "per_fault_set": per_fault}

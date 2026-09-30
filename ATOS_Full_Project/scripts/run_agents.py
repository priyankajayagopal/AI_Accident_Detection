"""Run the agent workflow on a synthetic incident (no video needed).

  python -m scripts.run_agents                 # full lifecycle with a simulated operator approval
  python -m scripts.run_agents --faults vlm_down,severity_missing   # fault-injection demo (fallback handlers)
"""
import argparse
import json

from agents.orchestrator import Orchestrator
from agents.tools.incident_tools import MemoryStore, create_incident_from_candidate
from config import camera
from tests.synthetic.synthetic_incidents import synthetic_candidate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--faults", default="")
    ap.add_argument("--seeds", type=int, default=2)
    a = ap.parse_args()
    store = MemoryStore()
    orch = Orchestrator(store, publisher=lambda e: print("  event:", e.get("type"), e.get("status", "")))
    cand, traffic = synthetic_candidate("accident")
    inc = create_incident_from_candidate(store, cand, camera("CAM001"), None, traffic)
    faults = set(filter(None, a.faults.split(",")))
    print(f"orchestrator engine: {orch.engine}\n[1] verification phase")
    inc = orch.verification_phase(inc.incident_id, faults)
    print("   status:", inc.status.value, "| severity:", inc.estimated_severity.level.value, "| flags:", inc.flags)
    if inc.status.value == "verified":
        print("[2] HUMAN operator approves")
        orch.approve(inc.incident_id, "operator1")
        print("[3] response phase (dispatch -> clearance -> simulation -> report)")
        inc = orch.response_phase(inc.incident_id, faults, seeds=list(range(1, a.seeds + 1)))
        print("   status:", inc.status.value, "| services:", (inc.dispatch or {}).get("services"))
        print("   simulation improvement %:", (inc.simulation or {}).get("improvement_pct"))
        print("   report:", inc.report_path)
        orch.close(inc.incident_id, "operator1")
    print("\nagent trace:")
    for t in store.traces(inc.incident_id):
        print(f"  {t['agent']:24s} {t['step']:18s} {t['decision']}")


if __name__ == "__main__":
    main()

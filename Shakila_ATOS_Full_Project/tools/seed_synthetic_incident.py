"""Insert a synthetic incident into the DATABASE (for dashboard demos without running video):
   python -m tools.seed_synthetic_incident"""
from agents.tools.incident_tools import create_incident_from_candidate
from config import camera
from server.db import init_db
from server.dependencies import get_orchestrator, get_store
from tests.synthetic.synthetic_incidents import synthetic_candidate

if __name__ == "__main__":
    init_db()
    cand, traffic = synthetic_candidate("accident")
    inc = create_incident_from_candidate(get_store(), cand, camera("CAM001"), None, traffic)
    inc = get_orchestrator().verification_phase(inc.incident_id)
    print("seeded incident", inc.incident_id, inc.status.value)

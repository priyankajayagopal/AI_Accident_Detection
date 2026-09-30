"""Shadow-mode soak: run the full perception+verification stack on footage WITHOUT acting, count alerts per hour.
   python -m tools.shadow_mode_soak --video data/raw/videos/demo_normal.mp4 --repeat 3"""
import argparse

from agents.orchestrator import Orchestrator
from agents.tools.incident_tools import MemoryStore, create_incident_from_candidate
from config import camera
from pipeline.pipeline import PerceptionPipeline

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--video", required=True); ap.add_argument("--repeat", type=int, default=1); a = ap.parse_args()
    store = MemoryStore(); orch = Orchestrator(store); secs = 0.0; alerts = 0
    for _ in range(a.repeat):
        pl = PerceptionPipeline("CAM001", a.video, save_evidence=True)
        cs = pl.run_video(a.video)
        secs += pl.buffer.buf[-1][0] / pl.geo.fps if pl.buffer.buf else 0
        for c in cs:
            inc = create_incident_from_candidate(store, c.model_dump(), camera("CAM001"), f"data/evidence/incidents/{c.candidate_id}", {})
            alerts += orch.verification_phase(inc.incident_id).status.value == "verified"
    print(f"footage {secs / 3600:.3f} h  alerts {alerts}  -> {alerts / max(1e-9, secs / 3600):.1f} false alarms/hour (shadow mode)")

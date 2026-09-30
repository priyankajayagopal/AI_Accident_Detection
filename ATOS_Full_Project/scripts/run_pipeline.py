"""Perception -> agents, offline (no server): video in, verified incident + (auto-approved) response out.

  python -m scripts.run_pipeline --video data/raw/videos/demo_accident_tbone.mp4 --auto-approve
"""
import argparse

from agents.orchestrator import Orchestrator
from agents.tools.incident_tools import MemoryStore, create_incident_from_candidate
from config import camera
from pipeline.pipeline import PerceptionPipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/raw/videos/demo_accident_tbone.mp4")
    ap.add_argument("--camera", default="CAM001")
    ap.add_argument("--auto-approve", action="store_true", help="simulate the human operator (demo only)")
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    store = MemoryStore()
    orch = Orchestrator(store)
    pl = PerceptionPipeline(a.camera, a.video)
    traffic = {}
    def on_frame(f, r): traffic.update(r.traffic)
    cands = pl.run_video(a.video, on_frame=None, on_candidate=None)
    print(f"perception: {len(cands)} proposal(s) at {pl.fps():.0f} FPS (detector={pl.detector.name})")
    for c in cands:
        d = c.model_dump()
        ev = f"data/evidence/incidents/{c.candidate_id}"
        inc = create_incident_from_candidate(store, d, camera(a.camera), ev, {"vehicle_count": 8, "density_pct": 57.0, "avg_speed_kmh": 12.0, "queue_length_veh": 3})
        inc = orch.verification_phase(inc.incident_id)
        print(f"  {c.subtype_hint:18s} t={c.video_time_s:4.1f}s -> {inc.status.value:12s} severity={inc.estimated_severity.level.value} flags={inc.flags}")
        if inc.status.value == "verified" and a.auto_approve:
            orch.approve(inc.incident_id, "operator1")
            inc = orch.response_phase(inc.incident_id, seeds=list(range(1, a.seeds + 1)))
            print(f"     dispatch={inc.dispatch['services']} delay reduction={inc.simulation['improvement_pct']['avg_delay_s']}% report={inc.report_path}")


if __name__ == "__main__":
    main()

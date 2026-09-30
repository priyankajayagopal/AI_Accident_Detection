"""Simulation tool: runs baseline vs treatment on the corridor and returns a SimulationResult dict."""
from typing import List, Optional

from config import cfg
from schemas.simulation import ScenarioMetrics, SimulationResult
from tools.sumo import microsim

HANDLING_S = {"low": 240.0, "medium": 300.0, "high": 420.0, "critical": 600.0, "unknown": 300.0}


def run_simulation(severity: str, blocked_ratio: float, seeds: Optional[List[int]] = None, plan: Optional[dict] = None) -> dict:
    p = {"blocked_lanes": 2 if blocked_ratio >= 1.0 else 1, "handling_s": HANDLING_S.get(severity, 300.0)}
    if plan:
        for a in plan.get("signal_actions", []):
            if a["action"] == "hold_red_main":
                p["hold_green"] = max(10.0, cfg("sumo")["signals"]["cycle_s"] - a["seconds"])
            if a["action"] == "extend_green_main":
                p["ext_s"] = a["seconds"]
    seeds = seeds or cfg("sumo")["seeds"][:4]
    runs = microsim.run_experiment(p, seeds)
    s = microsim.summarize(runs)
    keys = ScenarioMetrics.model_fields.keys()
    res = SimulationResult(engine="microsim", seeds=len(seeds),
                           baseline=ScenarioMetrics(**{k: s["aggregate"]["baseline"][k] for k in keys}),
                           treatment=ScenarioMetrics(**{k: s["aggregate"]["treatment"][k] for k in keys}),
                           improvement_pct=s["improvement_pct"], queue_series=s["queue_series"],
                           notes=f"blocked_lanes={p['blocked_lanes']}, handling={p['handling_s']}s after first responder arrival")
    return res.model_dump()

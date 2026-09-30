"""Severity agent: structured CV features -> gradient-boosted classifier (never LLM guessing from pixels)."""
import time

from agents.agent_state import AgentContext
from agents.tools.camera_tools import blocked_lanes
from safety.fallback_handlers import severity_fallback
from schemas.incident import EstimatedSeverity, SeverityLevel, UncertaintyLevel
from schemas.severity import SeverityFeatures
from workers.severity import SeverityEstimator, SeverityUnavailable


class SeverityAgent:
    name = "severity_agent"

    def __init__(self, estimator: SeverityEstimator = None):
        self.est = estimator or SeverityEstimator()

    def run(self, ctx: AgentContext) -> dict:
        t0 = time.perf_counter()
        c, tr = ctx.candidate, ctx.traffic or {}
        boxes = list(c.get("bboxes", {}).values())
        bl = blocked_lanes(c["camera_id"], boxes) if boxes else {"count": 0, "ratio": 0.0, "lane_ids": []}
        f = SeverityFeatures(collision_intensity=float(c["features"].get("peak_decel_ms2", 0)), vehicle_count=len(c["track_ids"]),
                             heavy_vehicle=int(any(v in ("truck", "bus") for v in c.get("vehicle_types", []))),
                             people_involved=int(c.get("people", 0)), blocked_lane_ratio=bl["ratio"], blocked_lanes=bl["count"],
                             impact_speed_kmh=float(c["features"].get("speed_before_ms", 0)) * 3.6,
                             traffic_density_pct=float(tr.get("density_pct", 0)), queue_length=int(tr.get("queue_length_veh", 0)))
        used = []
        try:
            if "severity_missing" in ctx.faults:
                raise SeverityUnavailable("injected fault")
            r = self.est.estimate(f)
        except Exception:
            r = severity_fallback(f)
            used.append("severity_fallback")
        out = {"level": r.level, "confidence": round(r.confidence, 3), "reasons": r.reasons, "blocked_lanes": bl["count"],
               "used_fallbacks": used}
        ctx.outputs["severity_features"] = f.model_dump()
        ctx.outputs["blocked_ratio"] = bl["ratio"]
        ctx.outputs["blocked_lane_ids"] = bl["lane_ids"]
        ctx.log(self.name, "severity", ["camera_tools.blocked_lanes", "workers.severity"], r.level, {"conf": out["confidence"], "features": f.model_dump()}, t0)
        return out

    def commit(self, ctx: AgentContext, out: dict):
        inc, f = ctx.incident, ctx.outputs["severity_features"]
        conf = out["confidence"]
        inc.estimated_severity = EstimatedSeverity(level=SeverityLevel(out["level"]), confidence=conf,
                                                   uncertainty=UncertaintyLevel.LOW if conf >= 0.8 else UncertaintyLevel.MEDIUM if conf >= 0.6 else UncertaintyLevel.HIGH,
                                                   reasons=out["reasons"])
        inc.vehicles_involved, inc.people_involved = f["vehicle_count"], f["people_involved"]
        inc.vehicle_types = list(ctx.candidate.get("vehicle_types", []))
        inc.blocked_lanes = out["blocked_lanes"]
        inc.impact_speed_kmh = round(f["impact_speed_kmh"], 1)
        tr = ctx.traffic or {}
        inc.traffic_density_pct = tr.get("density_pct")
        inc.avg_speed_kmh = tr.get("avg_speed_kmh")
        inc.queue_length_veh = tr.get("queue_length_veh")
        if out["used_fallbacks"]:
            inc.flags.append("severity_fallback")
            ctx.fallbacks_used += out["used_fallbacks"]
        ctx.store.save(inc)

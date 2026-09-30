"""Optional fallback supervisor: when an agent fails or the guardrail blocks it, pick the deterministic handler."""
import time

from agents.agent_state import AgentContext
from safety import audit_logger
from safety.fallback_handlers import dispatch_fallback, report_fallback, routing_fallback, severity_fallback


class FallbackSupervisor:
    name = "fallback_supervisor"

    def handle(self, ctx: AgentContext, key: str, reason) -> dict:
        t0 = time.perf_counter()
        inc = ctx.incident
        if key == "dispatcher":
            out = dispatch_fallback(inc.estimated_severity.level.value)
        elif key == "traffic_clearance":
            out = routing_fallback("J2-J3")
            from config import camera
            out["blocked_edge"] = camera(inc.location.camera_id).get("corridor_edge", "J2-J3")
        elif key == "reporting":
            out = {"text": report_fallback(inc)}
        elif key == "verifier":
            out = {"decision": "needs_review", "confidence": 0.5, "combined_score": 0.5, "subtype": "accident",
                   "reasons": ["verifier failed - operator must review the raw evidence"], "used_fallbacks": ["verifier_fallback"]}
            ctx.outputs["verifier_extra"] = {"classifier": {"accident_prob": 0.5, "predicted": "unknown", "probs": {}, "model_version": "none", "used_fallback": True},
                                             "vlm": {"used_fallback": True, "backend": "fallback", "latency_ms": 0, "verdict": {"reasons": ["n/a"], "confidence": 0}}}
        elif key == "severity":
            out = {"level": "high", "confidence": 0.4, "reasons": ["severity agent failed - conservative default"],
                   "blocked_lanes": 0, "used_fallbacks": ["severity_fallback"]}
        else:
            raise KeyError(key)
        ctx.fallbacks_used.append(f"{key}_fallback")
        inc.flags.append(f"{key}_fallback")
        audit_logger.log_event("fallback", inc.incident_id, self.name, {"agent": key, "reason": str(reason)[:300]})
        ctx.log(self.name, f"fallback:{key}", [], "deterministic handler used", {"reason": str(reason)[:200]}, t0)
        return out

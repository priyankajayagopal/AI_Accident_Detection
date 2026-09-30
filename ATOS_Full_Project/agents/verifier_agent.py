"""Verifier agent: combines classifier + VLM + rule score into VERIFIED / NEEDS_REVIEW / REJECTED."""
import time

from agents.agent_state import AgentContext
from agents.tools.evidence_tools import has_keyframes
from agents.tools.incident_tools import apply_transition
from config import cfg
from safety.fallback_handlers import classifier_fallback, vlm_fallback
from schemas.incident import IncidentStatus, IncidentSubtype
from workers import vlm_verify
from workers.classifier_verify import ClassifierUnavailable, ClassifierVerifier
from workers.vlm_verify import VLMUnavailable

_SUB = {"accident": IncidentSubtype.ACCIDENT, "near_miss": IncidentSubtype.NEAR_MISS,
        "stopped_vehicle": IncidentSubtype.STOPPED_VEHICLE, "congestion_anomaly": IncidentSubtype.CONGESTION_ANOMALY}


class VerifierAgent:
    name = "verifier_agent"

    def __init__(self, classifier: ClassifierVerifier = None, vlm_backend: str = None):
        self.classifier = classifier or ClassifierVerifier()
        self.vlm_backend = vlm_backend

    def run(self, ctx: AgentContext) -> dict:
        t0 = time.perf_counter()
        cand = ctx.candidate
        used = []
        # 1) classifier
        try:
            if "classifier_missing" in ctx.faults:
                raise ClassifierUnavailable("injected fault")
            cr = self.classifier.predict(cand["features"])
        except Exception as e:
            cr = classifier_fallback(cand["features"], str(e))
            used.append("classifier_fallback")
        # 2) VLM
        vlm_p, vlm = None, None
        try:
            if "vlm_down" in ctx.faults:
                raise VLMUnavailable("injected fault")
            if "vlm_invalid" in ctx.faults:
                raise VLMUnavailable("injected invalid JSON")
            if not has_keyframes(ctx.evidence_dir):
                raise VLMUnavailable("no keyframes")
            vlm = vlm_verify.verify(ctx.evidence_dir, self.vlm_backend)
            v = vlm.verdict
            vlm_p = v.confidence if v.is_accident else 1.0 - v.confidence
        except VLMUnavailable as e:
            vlm = vlm_fallback(str(e))
            used.append("vlm_fallback")
        # 3) combine
        w = dict(cfg("agents")["verifier"]["weights"])
        parts = {"classifier": cr.accident_prob, "rule": float(cand["score"])}
        if vlm_p is not None:
            parts["vlm"] = vlm_p
        tot = sum(w[k] for k in parts)
        combined = sum(w[k] * parts[k] for k in parts) / tot
        acc = cfg("agents")["verifier"]["accept_score"]
        reasons = [f"classifier: {cr.predicted} (accident prob {cr.accident_prob:.2f})",
                   f"rule score {cand['score']:.2f} from signals " + ", ".join(f"{k}={v:.2f}" for k, v in cand["signals"].items() if v > 0.05)]
        reasons += [f"VLM ({vlm.backend}): {r}" for r in vlm.verdict.reasons[:3]]
        if cr.predicted not in ("accident", "unknown") and cr.accident_prob < 0.5:
            decision, subtype = "rejected", cr.predicted
            reasons.append(f"classified as {cr.predicted}: logged for analytics, no operator alert")
        elif combined >= acc:
            decision, subtype = "verified", "accident"
        elif combined >= 0.45:
            decision, subtype = "needs_review", "accident"
            reasons.append("borderline evidence - operator review required")
        else:
            decision, subtype = "rejected", cr.predicted if cr.predicted in _SUB else "unknown"
            reasons.append("combined evidence below threshold")
        if used:
            reasons.append("fallback handlers used: " + ", ".join(used))
        out = {"decision": decision, "confidence": round(max(combined, 1 - combined), 3), "combined_score": round(combined, 3),
               "subtype": subtype, "reasons": reasons, "used_fallbacks": used}
        ctx.outputs["verifier_extra"] = {"classifier": cr.model_dump(), "vlm": vlm.model_dump()}
        ctx.log(self.name, "verify", ["classifier_verify", "vlm_verify"], decision,
                {"combined": out["combined_score"], "classifier": cr.accident_prob, "vlm": vlm_p}, t0)
        return out

    def commit(self, ctx: AgentContext, out: dict):
        inc = ctx.incident
        cr = ctx.outputs["verifier_extra"]["classifier"]
        vlm = ctx.outputs["verifier_extra"]["vlm"]
        inc.classifier_confidence = cr["accident_prob"]
        inc.vlm_confidence = None if vlm["used_fallback"] else vlm["verdict"]["confidence"]
        inc.subtype = _SUB.get(out["subtype"], IncidentSubtype.UNKNOWN)
        inc.verification = dict(out, classifier=cr, vlm=vlm)
        ctx.fallbacks_used += out["used_fallbacks"]
        if out["decision"] == "rejected":
            inc.rejection_reason = "; ".join(out["reasons"][-2:])
            apply_transition(ctx.store, inc, IncidentStatus.REJECTED, self.name, out["reasons"][-1], ctx.publisher)
            ctx.halted = True
        else:
            if out["decision"] == "needs_review":
                inc.flags.append("needs_review")
            if out["used_fallbacks"]:
                inc.flags.append("fallback_used")
            apply_transition(ctx.store, inc, IncidentStatus.VERIFIED, self.name, out["decision"], ctx.publisher)
            ctx.alert("warning" if out["decision"] == "needs_review" else "critical",
                      f"Accident {'needs review' if out['decision'] == 'needs_review' else 'verified'} at {inc.location.road_segment} "
                      f"({inc.location.camera_id}) - operator approval required")

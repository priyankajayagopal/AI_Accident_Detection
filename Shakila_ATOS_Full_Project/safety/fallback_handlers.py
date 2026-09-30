"""Six deterministic fallback handlers (no LLM). Used when a model / agent / tool fails."""
from typing import Any, Dict

from config import cfg
from schemas.classifier import ClassifierResult
from schemas.incident import IncidentRecord
from schemas.severity import SeverityFeatures, SeverityResult
from schemas.vlm import VLMResult, VLMVerdict


def vlm_fallback(reason: str) -> VLMResult:
    """VLM unavailable -> neutral verdict, flagged. Verifier then relies on classifier + rules."""
    v = VLMVerdict(is_accident=False, confidence=0.0, vehicles_visible=0, collision_visible=False,
                   vehicles_stationary_after=False, reasons=[f"VLM unavailable: {reason}"[:200]])
    return VLMResult(verdict=v, backend="fallback", latency_ms=0.0, used_fallback=True)


def classifier_fallback(features: Dict[str, float], reason: str) -> ClassifierResult:
    """Classifier failed -> use the raw rule score as accident probability."""
    p = float(min(1.0, max(0.0, features.get("score", 0.0))))
    return ClassifierResult(predicted="accident" if p >= 0.6 else "unknown", accident_prob=p,
                            probs={"accident": p}, model_version="rule_fallback", used_fallback=True)


def rule_severity(f: SeverityFeatures):
    """Rule table from the proposal (slide 10). Used (a) to label training data, (b) as the deterministic fallback."""
    r = cfg("severity")["rules"]
    if f.blocked_lane_ratio >= r["full_blockage_lanes_ratio"] or f.impact_speed_kmh >= r["critical_speed_kmh"] \
            or (f.people_involved > 0 and f.impact_speed_kmh >= 30) or (f.heavy_vehicle and f.impact_speed_kmh >= 45):
        return "critical", ["full blockage / very high impact speed / people or heavy vehicle at high speed"]
    if f.vehicle_count >= r["high_vehicles"] or f.people_involved > 0 or f.heavy_vehicle or f.blocked_lanes >= 2:
        return "high", ["multi-vehicle, heavy vehicle, pedestrian involved or 2+ lanes blocked"]
    if f.vehicle_count >= 2 or f.blocked_lanes >= 1:
        return "medium", ["two vehicles involved or one lane blocked"]
    return "low", ["single vehicle, no lane blocked"]


def severity_fallback(f: SeverityFeatures) -> SeverityResult:
    level, reasons = rule_severity(f)
    return SeverityResult(level=level, confidence=0.6, probs={level: 0.6}, reasons=reasons, used_fallback=True)


def dispatch_fallback(severity: str) -> Dict[str, Any]:
    a = cfg("agents")["dispatcher"]
    services = a["service_rules"].get(severity, ["police"])
    eta = {s: {"ambulance": 420, "police": 360, "fire": 540, "tow": 900}[s] for s in services}
    return {"services": services, "priority": a["base_priority"].get(severity, "P3"), "eta_s": eta,
            "rationale": f"Template dispatch for {severity} severity (fallback handler).",
            "advisory_only": True, "used_fallbacks": ["dispatch_fallback"]}


def routing_fallback(blocked_edge: str) -> Dict[str, Any]:
    """Static precomputed Route B around the corridor."""
    return {"diversion_route": ["J1", "A1", "A2", "A3", "J4"], "diversion_eta_s": 300.0,
            "emergency_route": ["S0", "J1", "J2"], "emergency_eta_s": 240.0, "blocked_edge": blocked_edge,
            "signal_actions": [{"junction": "J2", "action": "hold_red_main", "seconds": 20},
                               {"junction": "J3", "action": "extend_green_main", "seconds": 30}],
            "strategy": "Static diversion via Route B + upstream hold / downstream extension (fallback handler)",
            "actuation": "simulation_only", "used_fallbacks": ["routing_fallback"]}


def report_fallback(inc: IncidentRecord) -> str:
    return (f"# Incident report {inc.incident_id}\n\n(Fallback template - advisory only, human decision required)\n\n"
            f"- Camera: {inc.location.camera_id}\n- Status: {inc.status.value}\n"
            f"- Subtype: {inc.subtype.value}\n- Severity: {inc.estimated_severity.level.value}\n"
            f"- Created: {inc.created_at.isoformat()}\n")

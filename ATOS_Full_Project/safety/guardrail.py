"""Deterministic guardrails that check EVERY agent output before it is accepted."""
from typing import Any, Dict

from pydantic import ValidationError

from config import cfg
from schemas.agent_outputs import (ClearancePlan, DispatchPlan, GuardrailResult, SeverityOutput,
                                   VerifierOutput)
from schemas.incident import IncidentRecord, IncidentStatus

ALLOWED_SERVICES = {"ambulance", "police", "fire", "tow"}
REQUIRED_APPROVAL_STATES = {IncidentStatus.OPERATOR_APPROVED, IncidentStatus.DISPATCH_RECOMMENDED,
                            IncidentStatus.SIMULATED, IncidentStatus.CLOSED}


def _res(checked, violations, warnings=None):
    return GuardrailResult(passed=not violations, violations=violations, warnings=warnings or [], checked=checked)


def check_verifier(out: Dict[str, Any], incident: IncidentRecord) -> GuardrailResult:
    v = []
    try:
        o = VerifierOutput(**out)
    except ValidationError as e:
        return _res("verifier", [f"G1 schema: {e.errors()[0]['msg']}"])
    if o.decision == "verified" and o.combined_score < cfg("agents")["verifier"]["accept_score"] - 1e-9:
        v.append("G2 verified with combined_score below accept threshold")
    if incident.requires_human_approval is not True:
        v.append("G3 requires_human_approval must never be disabled")
    return _res("verifier", v)


def check_severity(out: Dict[str, Any], incident: IncidentRecord) -> GuardrailResult:
    try:
        o = SeverityOutput(**out)
    except ValidationError as e:
        return _res("severity", [f"G1 schema: {e.errors()[0]['msg']}"])
    v, w = [], []
    if o.level == "critical" and o.confidence < 0.4:
        w.append("G4 critical severity with low confidence - operator must confirm")
    return _res("severity", v, w)


def check_dispatch(out: Dict[str, Any], incident: IncidentRecord) -> GuardrailResult:
    v, w = [], []
    if incident.status not in REQUIRED_APPROVAL_STATES or not incident.human_approved:
        v.append("G5 dispatch recommendation produced before human approval")
    try:
        o = DispatchPlan(**out)
    except ValidationError as e:
        return _res("dispatcher", v + [f"G1 schema: {e.errors()[0]['msg']}"])
    if not set(o.services) <= ALLOWED_SERVICES:
        v.append("G6 unknown emergency service requested")
    sev = incident.estimated_severity.level.value
    if sev == "critical" and "ambulance" not in o.services:
        v.append("G7 critical severity requires an ambulance")
    if sev == "high" and "ambulance" not in o.services:
        v.append("G7 high severity requires an ambulance")
    for svc, eta in o.eta_s.items():
        if not (0 < eta < 3600):
            v.append(f"G8 implausible ETA for {svc}: {eta}")
    if not o.advisory_only:
        v.append("G9 dispatch must remain advisory (no autonomous actuation)")
    return _res("dispatcher", v, w)


def check_clearance(out: Dict[str, Any], incident: IncidentRecord) -> GuardrailResult:
    v = []
    if not incident.human_approved:
        v.append("G5 clearance plan produced before human approval")
    try:
        o = ClearancePlan(**out)
    except ValidationError as e:
        return _res("traffic_clearance", v + [f"G1 schema: {e.errors()[0]['msg']}"])
    c = cfg("agents")["clearance"]
    if o.actuation != "simulation_only":
        v.append("G10 signal actuation must stay simulation_only")
    be = tuple(o.blocked_edge.split("-"))
    for x, y in zip(o.diversion_route, o.diversion_route[1:]):
        if (x, y) == be:
            v.append("G11 diversion route uses the blocked edge")
    for s in o.signal_actions:
        if s.action == "extend_green_main" and s.seconds > c["max_green_extension_s"]:
            v.append(f"G12 green extension {s.seconds}s exceeds {c['max_green_extension_s']}s at {s.junction}")
        if s.action == "hold_red_main" and s.seconds > c["max_all_red_s"] + c["max_green_extension_s"]:
            v.append(f"G12 red hold {s.seconds}s too long at {s.junction}")
    if not (0 < o.emergency_eta_s < 3600):
        v.append("G8 implausible emergency ETA")
    return _res("traffic_clearance", v)


def check_report(text: str, incident: IncidentRecord) -> GuardrailResult:
    v = []
    if incident.incident_id not in text:
        v.append("G13 report missing incident id")
    if "advisory" not in text.lower():
        v.append("G14 report missing advisory / human-decision disclaimer")
    return _res("reporting", v)


CHECKS = {"verifier": check_verifier, "severity": check_severity, "dispatcher": check_dispatch,
          "traffic_clearance": check_clearance}

from safety import audit_logger, guardrail
from schemas.incident import IncidentLocation, IncidentRecord, IncidentStatus, EstimatedSeverity, SeverityLevel


def _inc(status, approved, sev="high"):
    i = IncidentRecord(location=IncidentLocation(camera_id="CAM001"), status=status, human_approved=approved,
                       estimated_severity=EstimatedSeverity(level=SeverityLevel(sev), confidence=0.9))
    return i


def test_dispatch_before_approval_blocked():
    r = guardrail.check_dispatch({"services": ["police"], "priority": "P3", "rationale": "x"}, _inc(IncidentStatus.VERIFIED, False))
    assert not r.passed and any("G5" in v for v in r.violations)


def test_critical_requires_ambulance():
    r = guardrail.check_dispatch({"services": ["police"], "priority": "P1", "rationale": "x"}, _inc(IncidentStatus.OPERATOR_APPROVED, True, "critical"))
    assert not r.passed and any("G7" in v for v in r.violations)


def test_actuation_must_be_simulation_only():
    plan = {"diversion_route": ["J1", "A1", "J3"], "diversion_eta_s": 100, "emergency_route": ["HOSP", "J1"], "emergency_eta_s": 100,
            "blocked_edge": "J2-J3", "signal_actions": [{"junction": "J3", "action": "extend_green_main", "seconds": 90}], "strategy": "s"}
    r = guardrail.check_clearance(plan, _inc(IncidentStatus.DISPATCH_RECOMMENDED, True))
    assert not r.passed and any("G12" in v for v in r.violations)


def test_diversion_cannot_use_blocked_edge():
    plan = {"diversion_route": ["J2", "J3"], "diversion_eta_s": 100, "emergency_route": ["HOSP", "J1"], "emergency_eta_s": 100,
            "blocked_edge": "J2-J3", "signal_actions": [], "strategy": "s"}
    assert not guardrail.check_clearance(plan, _inc(IncidentStatus.DISPATCH_RECOMMENDED, True)).passed


def test_audit_chain_detects_tampering(tmp_path):
    f = tmp_path / "a.log"
    for i in range(3):
        audit_logger.log_event("t", "x", "a", {"i": i}, file=f)
    assert audit_logger.verify_chain(f)[0]
    lines = f.read_text().splitlines()
    lines[1] = lines[1].replace('"i": 1', '"i": 9')
    f.write_text("\n".join(lines) + "\n")
    assert not audit_logger.verify_chain(f)[0]

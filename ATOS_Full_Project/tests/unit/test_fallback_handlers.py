from safety.fallback_handlers import (classifier_fallback, dispatch_fallback, report_fallback, routing_fallback, rule_severity,
                                      severity_fallback, vlm_fallback)
from schemas.severity import SeverityFeatures


def test_rule_table():
    assert rule_severity(SeverityFeatures(vehicle_count=1))[0] == "low"
    assert rule_severity(SeverityFeatures(vehicle_count=2, blocked_lanes=1))[0] == "medium"
    assert rule_severity(SeverityFeatures(vehicle_count=3))[0] == "high"
    assert rule_severity(SeverityFeatures(vehicle_count=2, blocked_lane_ratio=1.0, blocked_lanes=2))[0] == "critical"


def test_handlers_return_valid_objects():
    assert vlm_fallback("x").used_fallback
    assert classifier_fallback({"score": 0.7}, "x").accident_prob == 0.7
    assert severity_fallback(SeverityFeatures()).used_fallback
    assert "ambulance" in dispatch_fallback("critical")["services"]
    assert routing_fallback("J2-J3")["actuation"] == "simulation_only"

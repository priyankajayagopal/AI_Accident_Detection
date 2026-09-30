import pytest
from pydantic import ValidationError
from schemas.vlm import VLMVerdict
from schemas.agent_outputs import DispatchPlan


def test_vlm_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        VLMVerdict(is_accident=True, confidence=1.7, vehicles_visible=2, collision_visible=True, vehicles_stationary_after=True, reasons=["x"])


def test_vlm_requires_reasons():
    with pytest.raises(ValidationError):
        VLMVerdict(is_accident=True, confidence=0.9, vehicles_visible=2, collision_visible=True, vehicles_stationary_after=True, reasons=[])


def test_dispatch_rejects_unknown_service():
    with pytest.raises(ValidationError):
        DispatchPlan(services=["helicopter"], priority="P1", rationale="x")

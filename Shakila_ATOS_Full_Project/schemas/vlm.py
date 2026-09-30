"""Strict VLM output contract. Anything that fails validation -> fallback handler, never trusted."""
from typing import List
from pydantic import BaseModel, Field, field_validator


class VLMVerdict(BaseModel):
    is_accident: bool
    confidence: float = Field(ge=0.0, le=1.0)
    vehicles_visible: int = Field(ge=0, le=50)
    collision_visible: bool
    vehicles_stationary_after: bool
    reasons: List[str] = Field(min_length=1, max_length=6)

    @field_validator("reasons")
    @classmethod
    def _short(cls, v):
        return [r[:240] for r in v]


class VLMResult(BaseModel):
    verdict: VLMVerdict
    backend: str
    latency_ms: float
    used_fallback: bool = False

"""Severity estimator: gradient-boosted classifier over structured CV features (the LLM never guesses severity)."""
from typing import Optional

import joblib
import numpy as np

from config import cfg, path
from safety.fallback_handlers import rule_severity
from schemas.severity import SEVERITY_FEATURES, SeverityFeatures, SeverityResult


class SeverityUnavailable(Exception):
    pass


class SeverityEstimator:
    def __init__(self, model_path: Optional[str] = None):
        p = path(model_path or cfg("severity")["model_path"])
        self.bundle = joblib.load(p) if p.exists() else None
        self.path = p

    @property
    def available(self):
        return self.bundle is not None

    def estimate(self, f: SeverityFeatures) -> SeverityResult:
        if not self.available:
            raise SeverityUnavailable(f"model not found: {self.path} (run: python -m scripts.train_models)")
        d = f.model_dump()
        x = np.array([[float(d[n]) for n in SEVERITY_FEATURES]])
        m = self.bundle["model"]
        proba = m.predict_proba(x)[0]
        probs = {c: float(p) for c, p in zip(m.classes_, proba)}
        level = max(probs, key=probs.get)
        _, reasons = rule_severity(f)
        return SeverityResult(level=level, confidence=probs[level], probs=probs,
                              reasons=[f"model: {level} ({probs[level]:.0%})"] + reasons)

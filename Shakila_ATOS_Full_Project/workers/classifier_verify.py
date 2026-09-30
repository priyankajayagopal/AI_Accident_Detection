"""Stage-1 verifier: gradient-boosted classifier over the structured proposal features."""
import os
from typing import Dict, Optional

import joblib
import numpy as np

from config import cfg, path
from schemas.classifier import CLASSES, FEATURE_NAMES, ClassifierResult


class ClassifierUnavailable(Exception):
    pass


class ClassifierVerifier:
    def __init__(self, model_path: Optional[str] = None):
        self.path = path(model_path or cfg("classifier")["model_path"])
        self.bundle = None
        if self.path.exists():
            self.bundle = joblib.load(self.path)

    @property
    def available(self) -> bool:
        return self.bundle is not None

    def predict(self, features: Dict[str, float]) -> ClassifierResult:
        if not self.available:
            raise ClassifierUnavailable(f"model not found: {self.path} (run: python -m scripts.train_models)")
        x = np.array([[float(features.get(n, 0.0)) for n in self.bundle["feature_names"]]])
        proba = self.bundle["model"].predict_proba(x)[0]
        classes = list(self.bundle["model"].classes_)
        probs = {c: float(p) for c, p in zip(classes, proba)}
        top = max(probs, key=probs.get)
        return ClassifierResult(predicted=top, accident_prob=float(probs.get("accident", 0.0)), probs=probs,
                                model_version=self.bundle.get("version", "classifier_v1"))

"""Train (1) the accident/incident classifier on pipeline proposals, (2) the severity classifier.

  python -m scripts.train_models

Classifier: features come from REAL pipeline output (detect -> track -> candidate engine) on the train split;
labels from synthetic ground truth. Video-level split => no clip leakage.
Severity  : no public severity labels exist for CCTV, so labels come from the slide-10 rule table (+4 % noise);
            the model learns the table from structured features. Replace with CCD-derived labels for the thesis.
"""
import csv
import json
import random

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_recall_fscore_support

from config import cfg, path
from eval.common import candidates_for_split
from safety.fallback_handlers import rule_severity
from schemas.classifier import CLASSES, FEATURE_NAMES
from schemas.severity import SEVERITY_FEATURES, SeverityFeatures


def _xy(rows):
    X = np.array([[r["features"].get(n, 0.0) for n in FEATURE_NAMES] for r in rows], dtype=float)
    y = np.array([r["true_label"] for r in rows])
    return X, y


def binary_metrics(y_true, p_acc, thr):
    yt = np.array([1 if y == "accident" else 0 for y in y_true]); yp = (np.array(p_acc) >= thr).astype(int)
    tp = int(((yt == 1) & (yp == 1)).sum()); fp = int(((yt == 0) & (yp == 1)).sum())
    fn = int(((yt == 1) & (yp == 0)).sum()); tn = int(((yt == 0) & (yp == 0)).sum())
    pr = tp / max(1, tp + fp); rc = tp / max(1, tp + fn)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(pr, 3), "recall": round(rc, 3),
            "f1": round(2 * pr * rc / max(1e-9, pr + rc), 3), "fpr": round(fp / max(1, fp + tn), 3)}


def train_classifier():
    tr, va, te = (candidates_for_split(s) for s in ("train", "val", "test"))
    Xtr, ytr = _xy(tr); Xva, yva = _xy(va); Xte, yte = _xy(te)
    print(f"candidates  train={len(tr)} val={len(va)} test={len(te)}  classes(train)={dict(zip(*np.unique(ytr, return_counts=True)))}")
    g = cfg("classifier")["gradient_boosting"]
    m = GradientBoostingClassifier(**g).fit(np.vstack([Xtr]), ytr)
    out = {"n_candidates": {"train": len(tr), "val": len(va), "test": len(te)}}
    for name, X, y in (("val", Xva, yva), ("test", Xte, yte)):
        pred = m.predict(X)
        pa = m.predict_proba(X)[:, list(m.classes_).index("accident")]
        out[name] = {"accuracy": round(accuracy_score(y, pred), 3), "macro_f1": round(f1_score(y, pred, average="macro"), 3),
                     "accident_binary": binary_metrics(y, pa, cfg("classifier")["accident_prob_threshold"]),
                     "confusion": {"labels": list(m.classes_), "matrix": confusion_matrix(y, pred, labels=list(m.classes_)).tolist()}}
    out["feature_importance"] = {n: round(float(v), 3) for n, v in sorted(zip(FEATURE_NAMES, m.feature_importances_), key=lambda t: -t[1])}
    joblib.dump({"model": m, "feature_names": FEATURE_NAMES, "version": "classifier_v1"}, path(cfg("classifier")["model_path"]))
    json.dump(out, open(path(cfg("classifier")["metrics_path"]), "w"), indent=2)
    print("classifier  test:", out["test"]["accident_binary"], "macroF1", out["test"]["macro_f1"])


def synth_severity(n=6000, seed=7):
    rng = random.Random(seed); rows = []
    for _ in range(n):
        vc = rng.choices([1, 2, 3, 4], [0.25, 0.45, 0.20, 0.10])[0]
        bl = rng.choices([0, 1, 2, 3], [0.15, 0.40, 0.30, 0.15])[0]
        ratio = 0.0 if bl == 0 else 0.5 if bl == 1 else rng.choice([0.5, 1.0]) if bl == 2 else 1.0
        spd = min(100.0, rng.gammavariate(4, 9))
        f = SeverityFeatures(collision_intensity=round(spd * 0.35 + rng.gauss(0, 2), 2), vehicle_count=vc,
                             heavy_vehicle=int(rng.random() < 0.15), people_involved=int(rng.random() < 0.10),
                             blocked_lane_ratio=ratio, blocked_lanes=bl, impact_speed_kmh=round(spd, 1),
                             traffic_density_pct=round(rng.uniform(10, 100), 1), queue_length=rng.randint(0, 15))
        lvl = rule_severity(f)[0]
        order = ["low", "medium", "high", "critical"]
        if rng.random() < 0.04:
            lvl = order[max(0, min(3, order.index(lvl) + rng.choice([-1, 1])))]
        rows.append((f, lvl))
    return rows


def train_severity():
    rows = synth_severity()
    X = np.array([[getattr(f, n) for n in SEVERITY_FEATURES] for f, _ in rows], dtype=float)
    y = np.array([l for _, l in rows])
    n = len(rows); a, b = int(n * 0.70), int(n * 0.85)
    g = cfg("severity")["gradient_boosting"]
    m = GradientBoostingClassifier(**g).fit(X[:a], y[:a])
    res = {}
    for name, sl in (("val", slice(a, b)), ("test", slice(b, n))):
        pr = m.predict(X[sl])
        res[name] = {"accuracy": round(accuracy_score(y[sl], pr), 3), "macro_f1": round(f1_score(y[sl], pr, average="macro"), 3)}
    res["test"]["report"] = classification_report(y[b:], m.predict(X[b:]), output_dict=True, zero_division=0)
    joblib.dump({"model": m, "feature_names": SEVERITY_FEATURES, "version": "severity_v1"}, path(cfg("severity")["model_path"]))
    json.dump(res, open(path(cfg("severity")["metrics_path"]), "w"), indent=2)
    with open(path("data", "labels", "severity_labels.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(SEVERITY_FEATURES + ["severity"])
        for (ft, l) in rows[:1000]:
            w.writerow([getattr(ft, k) for k in SEVERITY_FEATURES] + [l])
    print("severity    test:", res["test"]["accuracy"], "macroF1", res["test"]["macro_f1"])


if __name__ == "__main__":
    train_classifier()
    train_severity()

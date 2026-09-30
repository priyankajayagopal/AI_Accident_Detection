"""VLM verification stage on held-out proposals: how well does it separate accidents from non-accidents?"""
from pathlib import Path

from eval.common import candidates_for_split
from workers import vlm_verify


def run(split="test", backend=None):
    tp = fp = fn = tn = skipped = 0
    for c in candidates_for_split(split):
        if not c["evidence_dir"] or not (Path(c["evidence_dir"]) / "after_raw.jpg").exists():
            skipped += 1
            continue
        try:
            r = vlm_verify.verify(c["evidence_dir"], backend)
        except Exception:
            skipped += 1
            continue
        pred, true = r.verdict.is_accident, c["true_label"] == "accident"
        tp += pred and true; fp += pred and not true; fn += (not pred) and true; tn += (not pred) and not true
    p, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return {"backend": backend or "mock", "tp": tp, "fp": fp, "fn": fn, "tn": tn, "skipped": skipped, "precision": round(p, 3),
            "recall": round(rc, 3), "f1": round(2 * p * rc / max(1e-9, p + rc), 3), "fpr": round(fp / max(1, fp + tn), 3)}

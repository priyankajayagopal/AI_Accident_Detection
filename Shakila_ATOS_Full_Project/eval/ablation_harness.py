"""Ablation (slide 18): single-model rules baseline vs +classifier vs +VLM (full two-stage verification)."""
from typing import Callable, Dict, List

from agents.orchestrator import Orchestrator
from agents.tools.incident_tools import MemoryStore, create_incident_from_candidate
from config import camera
from eval.common import candidates_for_split, load_split
from workers.classifier_verify import ClassifierVerifier


def _metrics(rows: List[dict], pred: Callable[[dict], bool], videos: List[dict]) -> Dict:
    tp = fp = fn = tn = 0
    for c in rows:
        p, t = pred(c), c["true_label"] == "accident"
        tp += p and t; fp += p and not t; fn += (not p) and t; tn += (not p) and not t
    pr, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
    # video-level false alarms
    fa_videos = len({c["video"] for c in rows if pred(c) and c["true_label"] != "accident"})
    n_neg = len([v for v in videos if v["label"] != "accident"])
    return {"precision": round(pr, 3), "recall": round(rc, 3), "f1": round(2 * pr * rc / max(1e-9, pr + rc), 3),
            "fpr_candidate": round(fp / max(1, fp + tn), 3), "false_alarm_videos": f"{fa_videos}/{n_neg}"}


def two_stage(cand: dict, use_vlm: bool, clf: ClassifierVerifier, cache: dict) -> bool:
    key = (cand["candidate_id"], use_vlm)
    if key in cache:
        return cache[key]
    store = MemoryStore()
    orch = Orchestrator(store, classifier=clf, engine="simple")
    inc = create_incident_from_candidate(store, cand, camera("CAM001"), cand["evidence_dir"], {})
    faults = set() if use_vlm else {"vlm_down"}
    res = orch.verification_phase(inc.incident_id, faults)
    ok = res.status.value == "verified" or "needs_review" in res.flags and res.status.value != "rejected"
    cache[key] = ok
    return ok


def run(split="test"):
    rows, videos = candidates_for_split(split), load_split(split)
    clf, cache = ClassifierVerifier(), {}
    out = {
        "A_rules_only (score>=0.60)": _metrics(rows, lambda c: c["score"] >= 0.60, videos),
        "B_rules_low_thr (score>=0.40, no verification)": _metrics(rows, lambda c: c["subtype_hint"] == "accident", videos),
        "C_classifier_only (no VLM)": _metrics(rows, lambda c: two_stage(c, False, clf, cache), videos),
        "D_full two-stage (classifier + VLM)": _metrics(rows, lambda c: two_stage(c, True, clf, cache), videos),
    }
    return out

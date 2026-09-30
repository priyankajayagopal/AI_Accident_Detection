"""False alarms per hour on footage with NO accident (normal / near-miss / stopped / congestion), full two-stage system."""
from eval.ablation_harness import two_stage
from eval.common import candidates_for_split, load_split
from workers.classifier_verify import ClassifierVerifier


def run(split="test"):
    clf, cache = ClassifierVerifier(), {}
    neg = [r for r in load_split(split) if r["label"] != "accident"]
    seconds = 16.0 * len(neg)
    cands = [c for c in candidates_for_split(split) if c["video"] in {r["video"] for r in neg}]
    fa = sum(1 for c in cands if two_stage(c, True, clf, cache))
    raw = len(cands)
    return {"negative_videos": len(neg), "footage_hours": round(seconds / 3600, 3), "raw_proposals": raw, "false_alarms_after_verification": fa,
            "false_alarms_per_hour": round(fa / (seconds / 3600), 2), "raw_proposals_per_hour": round(raw / (seconds / 3600), 2)}

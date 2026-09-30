"""Candidate-engine proposal recall and detection latency (impact -> proposal)."""
import numpy as np

from eval.common import candidates_for_split, load_split


def run(split="test"):
    cands = candidates_for_split(split)
    rows = load_split(split)
    acc_videos = [r for r in rows if r["label"] == "accident"]
    hit, lat = 0, []
    for r in acc_videos:
        cs = [c for c in cands if c["video"] == r["video"] and c["true_label"] == "accident"]
        if cs:
            hit += 1
            lat.append((min(c["frame_idx"] for c in cs) - int(r["impact_frame"])) / 20.0)
    per_label = {}
    for r in rows:
        n = len([c for c in cands if c["video"] == r["video"]])
        per_label.setdefault(r["label"], []).append(n)
    return {"accident_videos": len(acc_videos), "proposal_recall": round(hit / max(1, len(acc_videos)), 3),
            "latency_s_mean": round(float(np.mean(lat)), 2) if lat else None, "latency_s_max": round(float(np.max(lat)), 2) if lat else None,
            "proposals_per_video": {k: round(float(np.mean(v)), 2) for k, v in per_label.items()}}

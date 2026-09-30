"""Shared helpers for training / evaluation: splits, GT matching, candidate extraction (cached)."""
import csv
import json
import os
from pathlib import Path
from typing import Dict, List

from config import path
from pipeline.pipeline import PerceptionPipeline
from pipeline.tracker import iou

CACHE = path("data", "cache")


def load_split(name: str) -> List[dict]:
    p = path("data", "eval_splits", f"{name}.csv")
    with open(p) as f:
        return list(csv.DictReader(f))


def load_meta(video_rel: str) -> dict:
    with open(path(video_rel + ".json")) as f:
        return json.load(f)


def true_label(meta: dict, cand: dict) -> str:
    lab = meta["label"]
    if lab == "normal":
        return "no_incident"
    if lab == "congestion_anomaly":
        return lab if cand["subtype_hint"] == "congestion_anomaly" else "no_incident"
    gt = meta["gt"][min(cand["frame_idx"], len(meta["gt"]) - 1)]
    ids = set()
    for _, bb in cand["bboxes"].items():
        best, bi = None, 0.0
        for g in gt:
            o = iou(g["bbox"], bb)
            if o > bi:
                best, bi = g, o
        if best and bi > 0.3:
            ids.add(best["id"])
    ev = set((meta.get("event") or {}).get("ids", []))
    return lab if ids & ev else "no_incident"


def extract_video(video_rel: str, evidence_root=None, detector=None, engine_config=None) -> List[dict]:
    """Run the perception pipeline over one video; return labelled candidates (dicts)."""
    meta = load_meta(video_rel)
    pl = PerceptionPipeline("CAM001", str(path(video_rel)), detector=detector, save_evidence=evidence_root is not None,
                            engine_config=engine_config)
    if evidence_root is not None:
        import pipeline.pipeline as pp
        orig = pp.package
        pp.package = lambda c, buf, store, fps, root=None: orig(c, buf, store, fps, root=evidence_root)
    out = []
    try:
        for c in pl.run_video(str(path(video_rel))):
            d = c.model_dump()
            d["true_label"] = true_label(meta, d)
            d["video"] = video_rel
            d["scenario"] = meta["scenario"]
            d["impact_frame"] = (meta.get("event") or {}).get("impact_frame")
            d["evidence_dir"] = str(Path(evidence_root) / c.candidate_id) if evidence_root else None
            out.append(d)
    finally:
        if evidence_root is not None:
            pp.package = orig
    return out, pl.fps()


def candidates_for_split(split: str, force: bool = False) -> List[dict]:
    """Cached extraction (data/cache/cands_<split>.json)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"cands_{split}.json"
    if f.exists() and not force:
        return json.load(open(f))
    rows = []
    for r in load_split(split):
        cs, _ = extract_video(r["video"], evidence_root=CACHE / "evidence")
        rows += cs
    json.dump(rows, open(f, "w"))
    return rows

"""Saves the evidence bundle for a proposal: keyframes (before / impact / after), clip, trajectory plot, features."""
import json
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import path
from pipeline.track_features import TrackFeatureStore
from schemas.evidence import CandidateProposal, EvidenceBundle


class FrameBuffer:
    def __init__(self, seconds: float, fps: float):
        self.buf = deque(maxlen=int(seconds * fps))

    def push(self, idx, frame):
        self.buf.append((idx, frame))

    def nearest(self, idx):
        if not self.buf:
            return None
        return min(self.buf, key=lambda t: abs(t[0] - idx))


def package(c: CandidateProposal, buf: FrameBuffer, store: TrackFeatureStore, fps: float,
            root: Optional[Path] = None) -> EvidenceBundle:
    root = Path(root) if root else path("data", "evidence", "incidents")
    d = root / c.candidate_id
    d.mkdir(parents=True, exist_ok=True)
    kf = {}
    for name, idx in (("before", c.event_frame_idx - int(0.5 * fps)), ("impact", c.event_frame_idx), ("after", c.frame_idx)):
        hit = buf.nearest(idx)
        if hit is None:
            continue
        raw = hit[1]
        cv2.imwrite(str(d / f"{name}_raw.jpg"), raw)
        ann = raw.copy()
        for tid, b in c.bboxes.items():
            s = store.get(tid, hit[0])
            bb = s["bbox"] if s else b
            cv2.rectangle(ann, (int(bb[0]), int(bb[1])), (int(bb[2]), int(bb[3])), (40, 40, 240), 2)
        cv2.putText(ann, f"{name.upper()}  frame {hit[0]}", (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(str(d / f"{name}.jpg"), ann)
        kf[name] = str(d / f"{name}.jpg")
    clip = None
    if buf.buf:
        h, w = buf.buf[0][1].shape[:2]
        clip = str(d / "clip.mp4")
        vw = cv2.VideoWriter(clip, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        for _, fr in buf.buf:
            vw.write(fr)
        vw.release()
    plot = str(d / "trajectory.png")
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
    f0, f1 = c.event_frame_idx - int(3 * fps), c.frame_idx
    for tid in c.track_ids:
        xs = store.series(tid, "cx", f0, f1); ys = store.series(tid, "cy", f0, f1)
        sp = store.series(tid, "speed", f0, f1)
        if xs:
            ax[0].plot([v for _, v in xs], [v for _, v in ys], "-o", ms=2, label=f"track {tid}")
            ax[1].plot([(f - c.event_frame_idx) / fps for f, _ in sp], [v * 3.6 for _, v in sp], label=f"track {tid}")
    ax[0].invert_yaxis(); ax[0].set_title("Trajectories (image px)"); ax[0].legend(fontsize=7)
    ax[1].axvline(0, color="r", ls="--", lw=1); ax[1].set_title("Speed (km/h) vs time from event (s)")
    ax[1].set_xlabel("s"); ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(plot, dpi=90); plt.close(fig)
    fj = str(d / "candidate.json")
    with open(fj, "w") as f:
        json.dump(c.model_dump(), f, indent=2)
    return EvidenceBundle(directory=str(d), keyframes=kf, clip=clip, trajectory_plot=plot, features_json=fj)

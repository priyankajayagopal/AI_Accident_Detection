"""Run perception on one video, save the annotated output and candidate proposals.

  python -m scripts.process_video --video data/raw/videos/demo_accident_tbone.mp4 --out storage/exports/annotated.mp4
  python -m scripts.process_video --video my_cctv.mp4 --detector yolo      # real footage (pip install ultralytics)
"""
import argparse
import json

import cv2

from config import path
from pipeline.pipeline import PerceptionPipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--camera", default="CAM001")
    ap.add_argument("--detector", default=None, help="auto|yolo|color|motion")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-evidence", action="store_true")
    a = ap.parse_args()
    pl = PerceptionPipeline(a.camera, a.video, a.detector, save_evidence=not a.no_evidence)
    writer = None

    def on_frame(frame, res):
        nonlocal writer
        if a.out:
            img = pl.annotate(frame, res)
            if writer is None:
                h, w = img.shape[:2]
                writer = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), pl.geo.fps, (w, h))
            writer.write(img)

    cands = pl.run_video(a.video, on_frame=on_frame)
    if writer:
        writer.release()
    print(f"detector={pl.detector.name}  frames processed at {pl.fps():.0f} FPS  proposals={len(cands)}")
    for c in cands:
        print(f"  [{c.subtype_hint}] frame {c.frame_idx} ({c.video_time_s:.1f}s) score={c.score:.2f} tracks={c.track_ids}")
    json.dump([c.model_dump() for c in cands], open(path("storage", "exports", "last_proposals.json"), "w"), indent=2, default=str)


if __name__ == "__main__":
    main()

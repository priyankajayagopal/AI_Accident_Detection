"""MOTA and ID switches of the ByteTrack-style tracker vs synthetic ground truth."""
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from config import path
from eval.common import load_meta, load_split
from pipeline.detector import build_detector
from pipeline.tracker import ByteTrackLite, iou


def run(split="test", max_videos=8):
    fn = fp = idsw = gt_total = 0
    for r in load_split(split)[:max_videos]:
        meta = load_meta(r["video"])
        det, trk = build_detector("color", str(path(r["video"]))), ByteTrackLite()
        cap = cv2.VideoCapture(str(path(r["video"])))
        last = {}
        for f in range(meta["n_frames"]):
            ok, frame = cap.read()
            if not ok:
                break
            tr = trk.update(det.detect(frame), f)
            gts = meta["gt"][f]
            gt_total += len(gts)
            if not gts or not tr:
                fn += len(gts); fp += len(tr)
                continue
            C = np.array([[1 - iou(g["bbox"], t.bbox) for t in tr] for g in gts])
            ri, ci = linear_sum_assignment(C)
            matched_g = set()
            for i, j in zip(ri, ci):
                if C[i, j] <= 0.5:
                    gid, tid = gts[i]["id"], tr[j].id
                    matched_g.add(i)
                    if gid in last and last[gid] != tid:
                        idsw += 1
                    last[gid] = tid
                else:
                    fp += 1
            fn += len(gts) - len(matched_g)
            fp += len(tr) - len(ri)
        cap.release()
    mota = 1 - (fn + fp + idsw) / max(1, gt_total)
    return {"MOTA": round(mota, 3), "id_switches": idsw, "false_negatives": fn, "false_positives": fp, "gt_objects": gt_total}

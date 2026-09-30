"""Generate the synthetic dataset + labels + video-level 70/15/15 splits + 3 demo videos.

  python -m scripts.generate_synthetic_data                 # full set  (24 videos / scenario, ~5 min)
  python -m scripts.generate_synthetic_data --per-scenario 6   # quick set
  python -m scripts.generate_synthetic_data --demo-only        # only the 3 dashboard demo videos
"""
import argparse
import csv
import json
import random
from multiprocessing import Pool
from pathlib import Path

from config import cfg, path
from tools.synthetic_video import LABEL_OF, SCENARIOS, generate_video

VID = path("data", "raw", "videos")


def _job(a):
    sc, seed, out = a
    m = generate_video(sc, seed, out)
    return {"video": out, "scenario": sc, "label": LABEL_OF[sc], "seed": seed,
            "impact_frame": (m["event"] or {}).get("impact_frame", "")}


def make_demo():
    VID.mkdir(parents=True, exist_ok=True)
    for sc, seed, name in [("accident_tbone", 7, "demo_accident_tbone"), ("normal", 5, "demo_normal"),
                           ("accident_rearend", 9, "demo_accident_rearend")]:
        generate_video(sc, seed, str(VID / f"{name}.mp4"))
        print("demo video:", name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-scenario", type=int, default=cfg("evaluation")["synthetic"]["videos_per_scenario"])
    ap.add_argument("--demo-only", action="store_true")
    ap.add_argument("--extra-test", type=int, default=0, help="extra held-out videos per scenario appended to the test split")
    a = ap.parse_args()
    make_demo()
    if a.demo_only:
        return
    if a.extra_test:
        jobs = [(sc, 5000 + si * 100 + k, str(VID / f"{sc}_{5000 + si * 100 + k}.mp4")) for si, sc in enumerate(SCENARIOS) for k in range(a.extra_test)]
        with Pool(2) as p:
            rows = p.map(_job, jobs)
        with open(path("data", "eval_splits", "test.csv"), "a", newline="") as f:
            w = csv.writer(f)
            for r in rows:
                w.writerow([str(Path(r["video"]).relative_to(path())), r["scenario"], r["label"], r["seed"], r["impact_frame"]])
        print("appended", len(rows), "videos to test split")
        return
    jobs = []
    for si, sc in enumerate(SCENARIOS):
        for k in range(a.per_scenario):
            seed = 1000 + si * 100 + k
            jobs.append((sc, seed, str(VID / f"{sc}_{seed}.mp4")))
    with Pool(2) as p:
        rows = p.map(_job, jobs)
    rows = [dict(r, video=str(Path(r["video"]).relative_to(path()))) for r in rows]
    rng = random.Random(42)
    split = {}
    sp = cfg("evaluation")["split"]
    for sc in SCENARIOS:                                  # stratified, video-level (no clip leakage)
        vs = [r["video"] for r in rows if r["scenario"] == sc]
        rng.shuffle(vs)
        n_tr, n_va = round(len(vs) * sp["train"]), round(len(vs) * sp["val"])
        for i, v in enumerate(vs):
            split[v] = "train" if i < n_tr else ("val" if i < n_tr + n_va else "test")
    lab = path("data", "labels")
    lab.mkdir(parents=True, exist_ok=True)
    cols = ["video", "scenario", "label", "seed", "impact_frame"]
    for name, pred in (("incident_labels.csv", lambda r: r["label"] in ("accident",)),
                       ("hard_negatives.csv", lambda r: r["label"] != "accident")):
        with open(lab / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols + ["split"]); w.writeheader()
            for r in rows:
                if pred(r):
                    w.writerow({**{c: r[c] for c in cols}, "split": split[r["video"]]})
    with open(lab / "severity_labels.csv", "w", newline="") as f:
        f.write("# severity labels are produced by scripts/train_models.py from the rule table (slide 10)\n")
    for s in ("train", "val", "test"):
        with open(path("data", "eval_splits", f"{s}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
            for r in rows:
                if split[r["video"]] == s:
                    w.writerow({c: r[c] for c in cols})
    print("videos:", len(rows), {s: sum(1 for v in split.values() if v == s) for s in ("train", "val", "test")})


if __name__ == "__main__":
    main()

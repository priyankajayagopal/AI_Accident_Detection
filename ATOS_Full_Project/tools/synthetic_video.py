"""Synthetic CCTV-style intersection videos with ground truth.

Why: public datasets (DoTA, CADP...) are large and need a GPU to be useful in 2 days. This generator creates
overhead junction videos with *known* incidents so the whole pipeline (detect -> track -> propose -> verify ->
agents -> dashboard) can be run, tested and evaluated on any laptop. Replace with real footage later:
`python -m scripts.process_video --video your.mp4 --detector yolo`.

Scenarios: normal, accident_tbone, accident_rearend, near_miss, stopped_vehicle, congestion
"""
import json
import math
import random
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

W, H, FPS, PPM = 640, 360, 20, 8.0
E_LANES, W_LANES = [194, 222], [138, 166]        # y centres  (E = moving +x, W = moving -x)
S_LANES, N_LANES = [278, 306], [334, 362]        # x centres  (S = moving +y, N = moving -y)
KIND = {"car": (36, 18), "truck": (58, 22), "bike": (22, 10)}   # (length, width) px  (8 px = 1 m)
HUES = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165]
A_COMF = 0.08            # comfortable braking px/frame^2  (= 4 m/s^2)
MIN_GAP = 6.0

SCENARIOS = ["normal", "accident_tbone", "accident_rearend", "near_miss", "stopped_vehicle", "congestion"]
LABEL_OF = {"normal": "normal", "accident_tbone": "accident", "accident_rearend": "accident",
            "near_miss": "near_miss", "stopped_vehicle": "stopped_vehicle", "congestion": "congestion_anomaly"}


class Veh:
    def __init__(self, vid, kind, orient, sign, lane, spawn, pos, speed, designated=False):
        self.id, self.kind, self.orient, self.sign, self.lane = vid, kind, orient, sign, lane
        self.spawn, self.pos, self.speed, self.desired = spawn, pos, speed, speed
        self.target, self.decel = speed, 0.12
        self.events: List[tuple] = []
        self.evi = 0
        self.frozen = False
        self.ignore_leader = designated
        self.designated = designated
        self.lat_off, self.lat_v = 0.0, 0.0
        self.hue = 0
        self.gone = False

    @property
    def length(self): return KIND[self.kind][0]
    @property
    def width(self): return KIND[self.kind][1]

    def center(self):
        if self.orient == "h":
            return self.pos, self.lane + self.lat_off
        return self.lane + self.lat_off, self.pos

    def half(self):  # (half-x, half-y)
        return (self.length / 2, self.width / 2) if self.orient == "h" else (self.width / 2, self.length / 2)

    def bbox(self):
        cx, cy = self.center(); hx, hy = self.half()
        return (cx - hx, cy - hy, cx + hx, cy + hy)


def _lateral_range(v):
    b = v.bbox()
    return (b[1], b[3]) if v.orient == "h" else (b[0], b[2])


def _leader_limit(f: Veh, others: List[Veh]) -> float:
    best = 1e9
    fl = _lateral_range(f)
    fc = f.center()[0 if f.orient == "h" else 1]
    fh = f.half()[0 if f.orient == "h" else 1]
    for g in others:
        if g is f:
            continue
        gl = _lateral_range(g)
        if min(fl[1], gl[1]) - max(fl[0], gl[0]) < 2:
            continue
        same_flow = g.orient == f.orient and g.sign == f.sign
        if not (same_flow or g.frozen):
            continue
        gc = g.center()[0 if f.orient == "h" else 1]
        gh = g.half()[0 if f.orient == "h" else 1]
        d = (gc - fc) * f.sign
        if d <= 0:
            continue
        gap = d - gh - fh
        vl = g.speed if same_flow else 0.0
        lim = vl + math.sqrt(2 * A_COMF * max(0.0, gap - MIN_GAP))
        best = min(best, lim)
    return best


def _iou_hit(a, b, margin=0.0):
    return not (a[2] + margin <= b[0] or b[2] + margin <= a[0] or a[3] + margin <= b[1] or b[3] + margin <= a[1])


def simulate(vehs: List[Veh], n_frames: int):
    states = []
    for f in range(n_frames):
        active = [v for v in vehs if v.spawn <= f and not v.gone]
        for v in active:
            while v.evi < len(v.events) and v.events[v.evi][0] <= f:
                _, kind, a, b = v.events[v.evi]
                v.evi += 1
                if kind == "speed":
                    v.target, v.decel = a, b
                elif kind == "freeze":
                    v.target, v.decel, v.frozen = 0.0, a, True
                elif kind == "crash":
                    v.target, v.decel, v.frozen = 0.0, 1.0, True
                    v.ignore_leader = False
                    v.lat_v = a
        for v in active:
            limit = 1e9 if (v.frozen or v.ignore_leader) else _leader_limit(v, active)
            tgt = min(v.target, limit)
            if tgt < v.speed:
                v.speed = max(tgt, v.speed - max(v.decel, 0.12 if limit < v.target else 0.0))
            else:
                v.speed = min(tgt, v.speed + 0.06)
            v.pos += v.sign * v.speed
            v.lat_off += v.lat_v
            v.lat_v *= 0.8
            lim = W if v.orient == "h" else H
            if (v.sign > 0 and v.pos > lim + 90) or (v.sign < 0 and v.pos < -90):
                v.gone = True
        states.append({v.id: v.bbox() for v in active if not v.gone})
    return states


def _lane_defs():
    return ([("h", 1, y) for y in E_LANES] + [("h", -1, y) for y in W_LANES] +
            [("v", 1, x) for x in S_LANES] + [("v", -1, x) for x in N_LANES])


def _start_pos(orient, sign):
    if orient == "h":
        return -60.0 if sign > 0 else W + 60.0
    return -60.0 if sign > 0 else H + 60.0


def make_base(rng, n_frames, nid, exclude=(), min_spawn=None, h_headway=3.2, v_headway=7.5,
              speed_rng=(3.6, 5.4), prefill_s=6.0, only=None):
    min_spawn = min_spawn or {}
    out = []
    for (o, s, lane) in _lane_defs():
        if (o, s, lane) in exclude or (only and (o, s, lane) not in only):
            continue
        t = -prefill_s + rng.uniform(0, 2.0)
        t = max(t, min_spawn.get((o, s, lane), -1e9) / FPS)
        while t * FPS < n_frames:
            r = rng.random()
            kind = "car" if r < 0.80 else ("truck" if r < 0.92 else "bike")
            sp = rng.uniform(*speed_rng)
            spawn = max(0, int(t * FPS))
            pos = _start_pos(o, s) + s * sp * max(0, -t * FPS)
            out.append(Veh(nid[0], kind, o, s, lane + rng.uniform(-1.5, 1.5), spawn, pos, sp))
            nid[0] += 1
            t += max(1.0, rng.expovariate(1.0 / (h_headway if o == "h" else v_headway)))
    return out


def _designated_conflicts(vehs, states, allowed_pairs):
    bad = set()
    for f, st in enumerate(states):
        ids = list(st.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                if (a, b) in allowed_pairs or (b, a) in allowed_pairs:
                    continue
                if _iou_hit(st[a], st[b], margin=2.0):
                    bad.add((a, b))
    return bad


def _resolve_conflicts(rng, make_vehs_fn, n_frames, allowed_pairs, designated_ids):
    """Run simulate; drop non-designated vehicles that overlap others; repeat."""
    vehs = make_vehs_fn()
    for _ in range(25):
        for v in vehs:
            v.__init_state = None
        states = simulate(_clone(vehs), n_frames)
        bad = _designated_conflicts(vehs, states, allowed_pairs)
        if not bad:
            return vehs
        drop = set()
        for a, b in bad:
            cand = [x for x in (a, b) if x not in designated_ids]
            if cand:
                drop.add(max(cand))  # drop the later-spawned / higher id
        if not drop:
            return vehs
        vehs = [v for v in vehs if v.id not in drop]
    return vehs


def _clone(vehs):
    import copy
    return copy.deepcopy(vehs)


def _assign_hues(vehs, states):
    """Graph-colour vehicles so anything that is ever within 30 px gets a different hue (detector splits by hue)."""
    conflicts = {v.id: set() for v in vehs}
    for st in states:
        ids = list(st.keys())
        for i in range(len(ids)):
            bi = st[ids[i]]
            for j in range(i + 1, len(ids)):
                if _iou_hit(bi, st[ids[j]], margin=30.0):
                    conflicts[ids[i]].add(ids[j]); conflicts[ids[j]].add(ids[i])
    hue_of = {}
    for v in sorted(vehs, key=lambda x: (x.spawn, x.id)):
        used = {hue_of[c] for c in conflicts[v.id] if c in hue_of}
        free = [h for h in HUES if h not in used]
        hue_of[v.id] = free[0] if free else min(HUES, key=lambda h: sum(1 for c in conflicts[v.id] if hue_of.get(c) == h))
        v.hue = hue_of[v.id]


def _background():
    bg = np.full((H, W, 3), (70, 72, 70), np.uint8)
    for x0, y0, x1, y1 in [(0, 0, 256, 116), (384, 0, 640, 116), (0, 244, 256, 360), (384, 244, 640, 360)]:
        cv2.rectangle(bg, (x0, y0), (x1, y1), (105, 108, 105), -1)
        cv2.rectangle(bg, (x0 + 6, y0 + 6), (x1 - 6, y1 - 6), (88, 90, 88), -1)
    cv2.rectangle(bg, (0, 124), (W, 236), (95, 95, 95), -1)
    cv2.rectangle(bg, (264, 0), (376, H), (95, 95, 95), -1)
    for x in range(0, W, 24):
        if not 260 < x < 380:
            cv2.line(bg, (x, 180), (x + 12, 180), (235, 235, 235), 2)
            for y in (152, 208):
                cv2.line(bg, (x, y), (x + 8, y), (200, 200, 200), 1)
    for y in range(0, H, 24):
        if not 120 < y < 240:
            cv2.line(bg, (320, y), (320, y + 12), (235, 235, 235), 2)
            for x in (292, 348):
                cv2.line(bg, (x, y), (x + 8, y), (200, 200, 200), 1)
    for x in (256, 384):
        cv2.line(bg, (x, 124), (x, 236), (230, 230, 230), 3)
    for y in (116, 244):
        cv2.line(bg, (264, y), (376, y), (230, 230, 230), 3)
    return bg


def _bgr(h, s=230, v=210):
    return tuple(int(c) for c in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


def _draw(img, v, box):
    x0, y0, x1, y1 = [int(round(c)) for c in box]
    cv2.rectangle(img, (x0, y0), (x1, y1), _bgr(v.hue), -1)
    cv2.rectangle(img, (x0, y0), (x1, y1), (15, 15, 15), 1)
    w, h = x1 - x0, y1 - y0
    if v.kind != "bike" and w > 4 and h > 4:
        if v.orient == "h":
            cv2.rectangle(img, (x0 + w // 4, y0 + 3), (x0 + 3 * w // 4, y1 - 3), _bgr(v.hue, 230, 150), -1)
        else:
            cv2.rectangle(img, (x0 + 3, y0 + h // 4), (x1 - 3, y0 + 3 * h // 4), _bgr(v.hue, 230, 150), -1)


# ------------------------------------------------------------------ scenario builders
def _tbone(rng, nid, n_frames):
    sa = rng.choice([1, -1]); ya = rng.choice(E_LANES if sa > 0 else W_LANES)
    sb = rng.choice([1, -1]); mx = rng.choice(S_LANES if sb > 0 else N_LANES)
    tc = rng.randint(100, 140)
    va, vb = rng.uniform(4.2, 5.8), rng.uniform(3.8, 5.4)
    ka, kb = rng.choice(["car", "car", "truck"]), rng.choice(["car", "car", "bike"])
    A = Veh(nid[0], ka, "h", sa, ya, 0, 0, va, True); nid[0] += 1
    B = Veh(nid[0], kb, "v", sb, mx, 0, 0, vb, True); nid[0] += 1
    xa_tc = mx - sa * (B.half()[0] + A.half()[0] - 2)
    yb_tc = ya - sb * (A.half()[1] + B.half()[1] - 2)
    A.pos = xa_tc - sa * va * tc
    B.pos = yb_tc - sb * vb * tc
    A.events.append((tc, "crash", rng.choice([-1, 1]) * rng.uniform(0.5, 1.4), 0))
    B.events.append((tc, "crash", rng.choice([-1, 1]) * rng.uniform(0.5, 1.4), 0))
    excl = {("h", sa, ya), ("v", sb, mx)}
    mins = {k: tc + rng.randint(40, 90) for k in excl}
    return [A, B], excl, mins, {"impact_frame": tc, "ids": [A.id, B.id], "pair": (A.id, B.id)}


def _rearend(rng, nid, n_frames):
    s = rng.choice([1, -1]); y = rng.choice(E_LANES if s > 0 else W_LANES)
    tc = rng.randint(100, 140)
    vl, vf = rng.uniform(1.6, 2.4), rng.uniform(5.0, 6.0)
    L = Veh(nid[0], rng.choice(["car", "truck"]), "h", s, y, 0, 0, vl, True); nid[0] += 1
    F = Veh(nid[0], "car", "h", s, y, 0, 0, vf, True); nid[0] += 1
    xl_tc = rng.uniform(250, 400) if s > 0 else rng.uniform(240, 390)
    xf_tc = xl_tc - s * (L.half()[0] + F.half()[0] - 3)
    L.pos = xl_tc - s * vl * tc
    F.pos = xf_tc - s * vf * tc
    L.events.append((tc, "crash", rng.uniform(-0.5, 0.5), 0))
    F.events.append((tc, "crash", rng.uniform(-0.5, 0.5), 0))
    excl = {("h", s, y)}
    return [L, F], excl, {("h", s, y): tc + rng.randint(40, 90)}, {"impact_frame": tc, "ids": [L.id, F.id], "pair": (L.id, F.id)}


def _near_miss(rng, nid, n_frames):
    for _ in range(40):
        sa = rng.choice([1, -1]); ya = rng.choice(E_LANES if sa > 0 else W_LANES)
        sb = rng.choice([1, -1]); mx = rng.choice(S_LANES if sb > 0 else N_LANES)
        vb, va, dec = rng.uniform(4.6, 5.4), rng.uniform(5.5, 6.5), rng.uniform(0.16, 0.20)
        A = Veh(nid[0], "car", "h", sa, ya, 0, 0, va, True)
        B = Veh(nid[0] + 1, "car", "v", sb, mx, 0, 0, vb, True)
        gap = rng.uniform(4, 7)
        y_stop = ya - sb * (A.half()[1] + gap + B.half()[1])
        stopd = vb * vb / (2 * dec)
        y_brake = y_stop - sb * stopd
        tb = rng.randint(70, 100)
        tA = tb + int(vb / dec) - rng.randint(3, 6)
        B.pos = y_brake - sb * vb * tb
        A.pos = mx - sa * va * tA
        B.events.append((tb, "speed", 0.0, dec))
        B.events.append((tb + int(vb / dec) + 4, "speed", vb, 0.06))
        # verify no overlap
        st = simulate(_clone([A, B]), n_frames)
        gaps = []
        hit = False
        for s_ in st:
            if A.id in s_ and B.id in s_:
                a, b = s_[A.id], s_[B.id]
                if _iou_hit(a, b, 0.5):
                    hit = True
                dx = max(0, max(a[0] - b[2], b[0] - a[2])); dy = max(0, max(a[1] - b[3], b[1] - a[3]))
                gaps.append(math.hypot(dx, dy))
        if not hit and gaps and min(gaps) < 12:
            nid[0] += 2
            return [A, B], {("h", sa, ya), ("v", sb, mx)}, {}, {"impact_frame": tA, "ids": [A.id, B.id], "pair": None}
    raise RuntimeError("near miss build failed")


def _stopped(rng, nid, n_frames):
    s = rng.choice([1, -1]); y = rng.choice(E_LANES if s > 0 else W_LANES)
    v = Veh(nid[0], "car", "h", s, y, 0, 0, rng.uniform(3.8, 4.8), True); nid[0] += 1
    v.ignore_leader = False
    fs = rng.randint(60, 90)
    xs = rng.uniform(140, 200) if s > 0 else rng.uniform(440, 500)   # where it stops (before junction)
    dec = rng.uniform(0.07, 0.10)
    stopd = v.desired ** 2 / (2 * dec)
    v.pos = (xs - s * stopd) - s * v.desired * fs
    v.events.append((fs, "freeze", dec, 0))
    return [v], set(), {}, {"impact_frame": fs, "ids": [v.id], "pair": None}


def generate_video(scenario: str, seed: int, out_path: Optional[str] = None, seconds: float = 16.0,
                   noise: float = 3.0) -> Dict:
    assert scenario in SCENARIOS, scenario
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    n_frames = int(seconds * FPS)
    nid = [1]
    special, excl, mins, info = [], set(), {}, {}
    base_kw = {}
    if scenario == "accident_tbone":
        special, excl, mins, info = _tbone(rng, nid, n_frames)
    elif scenario == "accident_rearend":
        special, excl, mins, info = _rearend(rng, nid, n_frames)
    elif scenario == "near_miss":
        special, excl, mins, info = _near_miss(rng, nid, n_frames)
    elif scenario == "stopped_vehicle":
        special, excl, mins, info = _stopped(rng, nid, n_frames)
        excl = set()
    elif scenario == "congestion":
        base_kw = dict(h_headway=2.3, speed_rng=(1.0, 1.6), prefill_s=40.0,
                       only={("h", 1, y) for y in E_LANES} | {("h", -1, y) for y in W_LANES})
    if scenario == "near_miss":
        # keep the designated lanes free so timings hold, other lanes carry traffic
        pass
    designated = {v.id for v in special}
    allowed = {info["pair"]} if info.get("pair") else set()

    def build():
        base = make_base(rng, n_frames, nid, exclude=excl, min_spawn=mins, **base_kw)
        return _clone(special) + base

    vehs = _resolve_conflicts(rng, build, n_frames, allowed, designated)
    states = simulate(_clone(vehs), n_frames)
    _assign_hues(vehs, states)
    states = simulate(_clone(vehs), n_frames)
    by_id = {v.id: v for v in vehs}
    bg = _background()

    writer = None
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    noise_bank = [nrng.normal(0, noise, (H, W, 3)).astype(np.int16) for _ in range(6)] if noise > 0 else []
    gt = []
    for f, st in enumerate(states):
        img = bg.copy()
        order = sorted(st.keys(), key=lambda i: (1 if by_id[i].designated and by_id[i].kind != "bike" else 0, i))
        frame_gt = []
        for vid in order:
            box = st[vid]
            if box[2] < 0 or box[0] > W or box[3] < 0 or box[1] > H:
                continue
            _draw(img, by_id[vid], box)
            frame_gt.append({"id": vid, "bbox": [round(c, 1) for c in box], "kind": by_id[vid].kind})
        gt.append(frame_gt)
        if writer is not None:
            if noise > 0:
                nz = noise_bank[int(nrng.integers(0, len(noise_bank)))]
                img = np.clip(img.astype(np.int16) + nz, 0, 255).astype(np.uint8)
            writer.write(img)
    if writer is not None:
        writer.release()
    meta = {"scenario": scenario, "label": LABEL_OF[scenario], "seed": seed, "fps": FPS, "size": [W, H],
            "n_frames": n_frames, "px_per_meter": PPM, "event": info or None, "gt": gt,
            "video": str(out_path) if out_path else None}
    meta["event"] = {k: v for k, v in (info or {}).items() if k != "pair"} or None
    if out_path:
        with open(str(out_path) + ".json", "w") as f:
            json.dump(meta, f)
    return meta


def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=SCENARIOS)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    m = generate_video(a.scenario, a.seed, a.out or f"data/raw/videos/{a.scenario}_{a.seed}.mp4")
    print("wrote", m["video"], "event:", m["event"])


if __name__ == "__main__":
    _cli()

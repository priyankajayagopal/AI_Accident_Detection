"""Built-in microscopic traffic simulator for the 5-junction corridor (zero install, runs anywhere).

Same experiment design as the SUMO study in the proposal (slide 12):
  Baseline  = fixed-time signals, no diversion, manual detection, emergency vehicle stuck in the queue
  Treatment = agent-driven: early detection, diversion (variable message signs), upstream hold / downstream
              green extension, emergency signal pre-emption
Model: IDM car-following (dt = 1 s), 2-lane main road (eastbound), signals with a coordinated offset, an incident that
blocks lane(s) mid-block, 1-lane alternative road between J2 and J3 (Route B), an emergency vehicle.
Assumption stated in the thesis: the blocked lane is cleared `handling_s` after the first responder arrives, so faster
arrival shortens the blockage.
For SUMO/TraCI, see tools/sumo/run_baseline.py (optional engine).
"""
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from config import cfg

IDM = dict(a=1.4, b=2.0, T=1.5, s0=2.0, L=4.5)


@dataclass
class V:
    vid: int
    x: float
    v: float
    lane: int
    v0: float
    t_in: float
    divert: bool = False
    seen_vms: bool = False


def default_params() -> dict:
    c = cfg("sumo")
    return {
        "n_junctions": c["corridor"]["junctions"], "spacing": c["corridor"]["spacing_m"], "lanes": c["corridor"]["lanes"],
        "v0": c["corridor"]["speed_limit_ms"], "main_vph": c["demand"]["main_veh_per_hour"],
        "horizon": c["sim_seconds"], "dt": c["step_s"], "t_inc": c["incident"]["start_s"],
        "cycle": c["signals"]["cycle_s"], "green": c["signals"]["main_green_s"],
        "compliance": c["treatment"]["diversion_compliance"], "hold_green": c["treatment"]["upstream_hold_green_s"],
        "ext_s": c["treatment"]["downstream_extension_s"], "plan_latency": c["incident"]["detect_to_plan_latency_s"],
        "ev_dispatch_delay": c["emergency"]["dispatch_delay_s"], "station_m": c["emergency"]["station_distance_m"],
        "blocked_lanes": 1, "handling_s": 300.0, "baseline_report_delay": 150.0, "operator_approval_s": 30.0,
    }


class CorridorSim:
    def __init__(self, params: dict, treatment: bool, seed: int):
        self.p = params
        self.treat = treatment
        self.rng = random.Random(seed)
        n, sp = self.p["n_junctions"], self.p["spacing"]
        self.xj = [sp * (i + 1) for i in range(n)]              # stop lines J1..Jn
        self.x_end = sp * (n + 1)
        self.x_inc = (self.xj[1] + self.xj[2]) / 2               # between J2 and J3
        self.veh: List[V] = []
        self.nid = 0
        self.backlog = [[], []]                                  # per-lane vehicles waiting to enter
        self.alt: List[tuple] = []                               # (t_ready, V)
        self.alt_last_exit = -99.0
        self.inc_active = False
        self.t_clear: Optional[float] = None
        self.plan_active = False
        self.ev = None                                           # dict(x, t_arr)
        self.ev_arrival: Optional[float] = None
        self.done_delays: List[float] = []
        self.queue_series, self.speed_series = [], []

    # ------------------------------------------------------------- signals
    def green(self, j: int, t: float) -> bool:
        p = self.p
        cyc, g = p["cycle"], p["green"]
        off = j * p["spacing"] / p["v0"]
        if self.treat and self.plan_active and self.inc_active:
            if j == 1:            # J2 upstream: hold (shorter green -> metering)
                g = p["hold_green"]
            if j == 2:            # J3 downstream: extend green
                g = min(cyc - 10, g + p["ext_s"])
        if self.treat and self.ev is not None and self.ev_near(j):
            return True           # emergency pre-emption
        return ((t - off) % cyc) < g

    def ev_near(self, j: int) -> bool:
        return self.ev is not None and -60 < self.xj[j] - self.ev["x"] < 250

    # ------------------------------------------------------------- IDM
    @staticmethod
    def idm(v, v0, gap, dv):
        s_star = IDM["s0"] + max(0.0, v * IDM["T"] + v * dv / (2 * math.sqrt(IDM["a"] * IDM["b"])))
        return IDM["a"] * (1 - (v / v0) ** 4 - (s_star / max(gap, 0.1)) ** 2)

    def new_vehicle(self, t, lane):
        self.nid += 1
        return V(self.nid, 0.0, self.p["v0"] * 0.9, lane, self.p["v0"] * self.rng.uniform(0.9, 1.1), t)

    # ------------------------------------------------------------- run
    def run(self) -> dict:
        p, dt = self.p, self.p["dt"]
        rate = p["main_vph"] / 3600.0 / p["lanes"]
        steps = int(p["horizon"] / dt)
        t_clear_forced = None
        for k in range(steps):
            t = k * dt
            # incident timeline
            if not self.inc_active and t >= p["t_inc"] and self.t_clear is None:
                self.inc_active = True
                delay = (p["plan_latency"] + p["operator_approval_s"]) if self.treat else p["baseline_report_delay"]
                self.t_dispatch = t + delay
                if self.treat:
                    self.plan_activation = t + p["plan_latency"]
            if self.treat and self.inc_active and not self.plan_active and t >= self.plan_activation:
                self.plan_active = True
            # emergency vehicle
            if self.inc_active and self.ev is None and self.ev_arrival is None and t >= self.t_dispatch:
                self.ev = {"x": -p["station_m"], "t0": t}
            if self.ev is not None:
                self._move_ev(t, dt)
            if self.inc_active and self.ev_arrival is not None and self.t_clear is None:
                self.t_clear = self.ev_arrival + p["handling_s"]
            if self.inc_active and self.t_clear is not None and t >= self.t_clear:
                self.inc_active = False
            # arrivals
            for lane in range(p["lanes"]):
                if self.rng.random() < rate * dt:
                    self.backlog[lane].append(self.new_vehicle(t, lane))
                if self.backlog[lane]:
                    ahead = [v for v in self.veh if v.lane == lane and v.x < 60]
                    if not ahead or min(v.x for v in ahead) > 14 + 0.6 * self.backlog[lane][0].v:
                        self.veh.append(self.backlog[lane].pop(0))
            self._alt_release(t)
            self._step_vehicles(t, dt)
            mv = [v for v in self.veh]
            self.speed_series.append(float(np.mean([v.v for v in mv])) if mv else p["v0"])
            self.queue_series.append(sum(1 for v in mv if v.v < 1.5 and v.x < self.x_inc + 5 and v.x > self.xj[0] - 250))
        return self._metrics()

    # ------------------------------------------------------------- emergency vehicle
    def _move_ev(self, t, dt):
        p = self.p
        ev = self.ev
        ahead = [v.v for v in self.veh if 0 <= v.x - ev["x"] < 200]
        jam = (float(np.mean(ahead)) / p["v0"]) if ahead else 1.0
        speed = 22.0 * min(1.0, jam + 0.25)
        if not self.treat:
            for j in range(len(self.xj)):
                if 0 < self.xj[j] - ev["x"] < 30 and not self.green(j, t):
                    speed = min(speed, 6.0)                      # cautious red-light crossing without pre-emption
        ev["x"] += speed * dt
        if ev["x"] >= self.x_inc - 25 and self.ev_arrival is None:
            self.ev_arrival = t
            self.ev = None

    # ------------------------------------------------------------- vehicles
    def _alt_release(self, t):
        """Vehicles finishing the alternative road merge back into the main road just after J3 (gap acceptance)."""
        self.alt.sort(key=lambda a: a[0])
        xr = self.xj[2] + 15
        placed = []
        for item in self.alt:
            t_ready, v = item
            if t_ready > t:
                break
            if t - self.alt_last_exit < 1.2:
                break
            for lane in (0, 1):
                if lane < (self.p["blocked_lanes"] if self.inc_active else 0) and xr < self.x_inc:
                    continue
                ok = all(not (-(6 + 0.6 * u.v) < (u.x - xr) < 14 + 0.3 * u.v) for u in self.veh if u.lane == lane)
                if ok:
                    v.x, v.v, v.lane = xr, 9.0, lane
                    self.alt_last_exit = t
                    self.veh.append(v)
                    placed.append(item)
                    break
        for it in placed:
            self.alt.remove(it)

    def _step_vehicles(self, t, dt):
        p = self.p
        blocked = p["blocked_lanes"] if self.inc_active else 0
        # lane changes near the obstacle
        for v in self.veh:
            if v.lane < blocked and 0 < self.x_inc - v.x < 180 and p["lanes"] > blocked:
                tgt = blocked  # first free lane
                ok = True
                for u in self.veh:
                    if u.lane == tgt and -14 - 0.7 * u.v < (u.x - v.x) < 14 + 0.3 * v.v:
                        ok = False
                        break
                if ok:
                    v.lane = tgt
        # treatment: VMS at J1 -> decide diversion
        if self.treat and self.plan_active and self.inc_active:
            for v in self.veh:
                if not v.seen_vms and v.x >= 100:
                    v.seen_vms = True
                    v.divert = self.rng.random() < p["compliance"]
        by_lane: Dict[int, List[V]] = {}
        for v in self.veh:
            by_lane.setdefault(v.lane, []).append(v)
        remove = []
        for lane, lst in by_lane.items():
            lst.sort(key=lambda a: -a.x)
            for i, v in enumerate(lst):
                acc = self.idm(v.v, v.v0, 1e4, 0.0)
                if i > 0:
                    L = lst[i - 1]
                    acc = min(acc, self.idm(v.v, v.v0, L.x - v.x - IDM["L"], v.v - L.v))
                if lane < blocked and v.x < self.x_inc:
                    acc = min(acc, self.idm(v.v, v.v0, self.x_inc - v.x - IDM["L"], v.v))
                for j, xs in enumerate(self.xj):
                    d = xs - v.x
                    if 0 < d < 90 and not self.green(j, t) and not (v.divert and j == 0):
                        if d > v.v * v.v / 8.0 or v.v < 3:
                            acc = min(acc, self.idm(v.v, v.v0, d, v.v))
                        break
                acc = max(acc, -6.0)
                v.v = max(0.0, v.v + acc * dt)
                v.x += v.v * dt
        for v in self.veh:
            if v.divert and v.x >= self.xj[0] - 6 and v.x < self.xj[0] + 60:
                remove.append(v)
                self.alt.append((t + 1000.0 / 9.0, v))
                v.divert = False
            elif v.x >= self.x_end:
                remove.append(v)
                self.done_delays.append((t - v.t_in) - self.x_end / v.v0)
        if remove:
            ids = {v.vid for v in remove}
            self.veh = [v for v in self.veh if v.vid not in ids]

    # ------------------------------------------------------------- metrics
    def _metrics(self) -> dict:
        p = self.p
        t_inc = p["t_inc"]
        horizon = p["horizon"]
        pending = [(horizon - v.t_in) - v.x / v.v0 for v in self.veh] + \
                  [(horizon - v.t_in) - 0.0 for lane in self.backlog for v in lane] + \
                  [(horizon - v.t_in) - self.xj[0] / v.v0 for _, v in self.alt]
        delays = self.done_delays + pending
        speeds = np.array(self.speed_series)
        v_norm = float(np.mean(speeds[60:int(t_inc)])) if t_inc > 60 else float(np.mean(speeds))
        q = np.array(self.queue_series)
        t_clear = self.t_clear if self.t_clear is not None else horizon
        tc = int(min(t_clear, horizon - 1))
        # queue dissipation: time after clearance until queue < 5 vehicles (censored at horizon)
        diss = horizon - t_clear
        for k in range(tc, len(q)):
            if q[k] < 5:
                diss = k - t_clear
                break
        # congestion recovery: time from incident start to 90 % of normal speed (60 s rolling), after clearance
        rec = horizon - t_inc
        for k in range(max(tc, 60), len(speeds)):
            if np.mean(speeds[k - 60:k]) >= 0.9 * v_norm and q[k] < 5:
                rec = k - t_inc
                break
        ev_t = (self.ev_arrival - t_inc) if self.ev_arrival is not None else horizon - t_inc
        return {"emergency_arrival_s": float(ev_t), "queue_dissipation_s": float(max(0.0, diss)),
                "avg_delay_s": float(np.mean(delays)) if delays else 0.0, "recovery_s": float(rec),
                "max_queue_veh": float(q.max()) if len(q) else 0.0, "vehicles_completed": float(len(self.done_delays)),
                "queue_series": q.tolist(), "t_clear": float(t_clear)}


def run_experiment(params: Optional[dict] = None, seeds: Optional[List[int]] = None) -> dict:
    p = default_params()
    if params:
        p.update(params)
    seeds = seeds or cfg("sumo")["seeds"]
    out = {"baseline": [], "treatment": []}
    for s in seeds:
        out["baseline"].append(CorridorSim(p, False, s).run())
        out["treatment"].append(CorridorSim(p, True, s).run())
    return out


def summarize(runs: dict, p: Optional[dict] = None) -> dict:
    keys = ["emergency_arrival_s", "queue_dissipation_s", "avg_delay_s", "recovery_s", "max_queue_veh", "vehicles_completed"]
    agg = {}
    for scen in ("baseline", "treatment"):
        agg[scen] = {k: float(np.mean([r[k] for r in runs[scen]])) for k in keys}
        agg[scen + "_std"] = {k: float(np.std([r[k] for r in runs[scen]])) for k in keys}
    imp = {}
    for k in keys[:5]:
        b, t = agg["baseline"][k], agg["treatment"][k]
        imp[k] = round(100.0 * (b - t) / b, 1) if b > 1e-9 else 0.0
    def sm(a, w=20):
        return np.convolve(np.pad(a, (w // 2, w - w // 2 - 1), mode="edge"), np.ones(w) / w, mode="valid")
    for scen in ("baseline", "treatment"):
        for r in runs[scen]:
            r["queue_series_smooth"] = sm(np.array(r["queue_series"], float)).tolist()
    n = min(len(runs["baseline"][0]["queue_series"]), 400)
    step = max(1, len(runs["baseline"][0]["queue_series"]) // n)
    series = {"t": list(range(0, len(runs["baseline"][0]["queue_series"]), step)),
              "baseline": [float(np.mean([r["queue_series_smooth"][i] for r in runs["baseline"]])) for i in range(0, len(runs["baseline"][0]["queue_series"]), step)],
              "treatment": [float(np.mean([r["queue_series_smooth"][i] for r in runs["treatment"]])) for i in range(0, len(runs["treatment"][0]["queue_series"]), step)]}
    return {"aggregate": agg, "improvement_pct": imp, "queue_series": series}

"""Road graph + time-dependent Dijkstra / A* for diversion routes and emergency corridors (slide 7).

Corridor (schematic, 400 m spacing):   HOSP --- J1 --- J2 --- J3 --- J4 --- J5 --- FIRE
                                                 |      |      |      |      |
Route B (alternative road)                       A1 --- A2 --- A3 --- A4 --- A5      POL --- J1
"""
import heapq
import math
from typing import Callable, Dict, List, Optional, Set, Tuple

# node -> (x, y) schematic coordinates (x east, y north) in units of 100 m
NODES: Dict[str, Tuple[float, float]] = {
    "HOSP": (-14, 0), "POL": (-8, 3), "FIRE": (54, 0),
    "J1": (4, 0), "J2": (8, 0), "J3": (12, 0), "J4": (16, 0), "J5": (20, 0),
    "A1": (4, -3), "A2": (8, -3), "A3": (12, -3), "A4": (16, -3), "A5": (20, -3),
}

# directed edges: (u, v) -> dict(length_m, speed_ms, kind)
EDGES: Dict[Tuple[str, str], dict] = {}


def _bi(u, v, length, speed, kind):
    EDGES[(u, v)] = {"length": length, "speed": speed, "kind": kind}
    EDGES[(v, u)] = {"length": length, "speed": speed, "kind": kind}


_bi("HOSP", "J1", 1800, 16.0, "arterial")
_bi("POL", "J1", 1000, 14.0, "arterial")
_bi("J5", "FIRE", 1500, 16.0, "arterial")
for a, b in [("J1", "J2"), ("J2", "J3"), ("J3", "J4"), ("J4", "J5")]:
    _bi(a, b, 400, 13.9, "corridor")
for i in range(1, 6):
    _bi(f"J{i}", f"A{i}", 100, 8.0, "link")
for i in range(1, 5):
    _bi(f"A{i}", f"A{i+1}", 400, 9.0, "routeB")

ADJ: Dict[str, List[str]] = {}
for (u, v) in EDGES:
    ADJ.setdefault(u, []).append(v)


def edge_key(s: str) -> Tuple[str, str]:
    a, b = s.split("-")
    return a, b


def peak_factor(t: float, kind: str) -> float:
    """Congestion multiplier on free-flow speed (time-dependent). t in seconds since midnight (or scenario start)."""
    if kind != "corridor":
        return 1.0
    hour = (t / 3600.0) % 24
    peak = math.exp(-((hour - 18.0) ** 2) / 2.0) + math.exp(-((hour - 9.0) ** 2) / 2.0)   # evening + morning peaks
    return 1.0 - 0.45 * min(1.0, peak)


def travel_time(u: str, v: str, t: float, blocked: Set[Tuple[str, str]], blocked_penalty: float = 4.0,
                emergency: bool = False) -> float:
    e = EDGES[(u, v)]
    f = peak_factor(t, e["kind"])
    speed = e["speed"] * f
    if emergency:
        speed = e["speed"] * (0.5 + 0.5 * f) * 1.35          # sirens: less congestion impact, higher speed
    tt = e["length"] / max(speed, 0.5)
    if (u, v) in blocked:
        tt *= 1.0 if emergency else blocked_penalty
    return tt


def dijkstra(src: str, dst: str, t0: float = 0.0, blocked_edges: Optional[Set[Tuple[str, str]]] = None,
             forbid: Optional[Set[Tuple[str, str]]] = None, emergency: bool = False) -> Tuple[List[str], float]:
    """Time-dependent Dijkstra (FIFO edge costs). forbid = edges that may not be used at all."""
    blocked = blocked_edges or set()
    forbid = forbid or set()
    best = {src: t0}
    prev: Dict[str, str] = {}
    pq = [(t0, src)]
    while pq:
        t, u = heapq.heappop(pq)
        if u == dst:
            break
        if t > best.get(u, 1e18):
            continue
        for v in ADJ.get(u, []):
            if (u, v) in forbid:
                continue
            nt = t + travel_time(u, v, t, blocked, emergency=emergency)
            if nt < best.get(v, 1e18):
                best[v], prev[v] = nt, u
                heapq.heappush(pq, (nt, v))
    if dst not in best:
        raise ValueError(f"no route {src}->{dst}")
    path, n = [dst], dst
    while n != src:
        n = prev[n]
        path.append(n)
    return path[::-1], best[dst] - t0


def astar(src: str, dst: str, t0: float = 0.0, blocked_edges=None, forbid=None) -> Tuple[List[str], float]:
    """A* with Euclidean heuristic (admissible: max speed 22 m/s). Same answer as dijkstra, fewer expansions."""
    blocked, forbid = blocked_edges or set(), forbid or set()
    vmax = 22.0

    def h(n):
        (x1, y1), (x2, y2) = NODES[n], NODES[dst]
        return math.hypot(x1 - x2, y1 - y2) * 100.0 / vmax

    g = {src: t0}
    prev = {}
    pq = [(t0 + h(src), src)]
    while pq:
        _, u = heapq.heappop(pq)
        if u == dst:
            break
        for v in ADJ.get(u, []):
            if (u, v) in forbid:
                continue
            nt = g[u] + travel_time(u, v, g[u], blocked)
            if nt < g.get(v, 1e18):
                g[v], prev[v] = nt, u
                heapq.heappush(pq, (nt + h(v), v))
    path, n = [dst], dst
    while n != src:
        n = prev[n]
        path.append(n)
    return path[::-1], g[dst] - t0


def plan_diversion(blocked_edge: str, t0: float = 0.0) -> Tuple[List[str], float]:
    """Route B: from the junction upstream of the blocked directed edge to the junction downstream, without using it."""
    u, v = edge_key(blocked_edge)
    forbid = {(u, v)}
    # advance diversion (VMS one junction earlier, before the queue tail): leave the corridor at J{i-1}
    up = f"J{int(u[1:]) - 1}" if u.startswith("J") and int(u[1:]) > 1 else u
    if up != u:
        forbid.add((up, u))
    path, tt = dijkstra(up, v, t0, forbid=forbid)
    return path, tt


def plan_emergency(service: str, blocked_edge: str, t0: float = 0.0) -> Tuple[List[str], float]:
    """Fastest emergency route to the incident: approach from either side of the blocked directed edge.
    Adds the last 200 m along the edge (half its length)."""
    station = {"ambulance": "HOSP", "police": "POL", "fire": "FIRE", "tow": "POL"}[service]
    u, v = edge_key(blocked_edge)
    half = EDGES[(u, v)]["length"] / 2 / (EDGES[(u, v)]["speed"] * 1.35)
    best = None
    for access in (u, v):
        try:
            path, tt = dijkstra(station, access, t0, blocked_edges={(u, v)}, emergency=True)
        except ValueError:
            continue
        tt += half
        if best is None or tt < best[1]:
            best = (path, tt)
    if best is None:
        raise ValueError("no emergency route")
    return best


def k_alternatives(src: str, dst: str, k: int = 2, t0: float = 0.0) -> List[Tuple[List[str], float]]:
    """Penalty method: repeatedly penalise edges of found routes to get diverse alternatives."""
    out, forbid = [], set()
    for _ in range(k):
        try:
            p, tt = dijkstra(src, dst, t0, forbid=set(forbid))
        except ValueError:
            break
        out.append((p, tt))
        mid = list(zip(p, p[1:]))
        if len(mid) > 1:
            forbid.add(mid[len(mid) // 2])
    return out


def graph_geojson() -> dict:
    """Nodes + edges for the dashboard map (schematic coordinates)."""
    return {"nodes": [{"id": n, "x": xy[0], "y": xy[1]} for n, xy in NODES.items()],
            "edges": [{"u": u, "v": v, "kind": e["kind"]} for (u, v), e in EDGES.items() if u < v]}

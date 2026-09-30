"""Tool wrappers around tools/routing.py (time-dependent Dijkstra)."""
from tools import routing


def diversion(blocked_edge: str, t0: float = 0.0):
    return routing.plan_diversion(blocked_edge, t0)


def emergency(service: str, blocked_edge: str, t0: float = 0.0):
    return routing.plan_emergency(service, blocked_edge, t0)


def graph():
    return routing.graph_geojson()

"""Simulation study: baseline (fixed-time, no diversion) vs agent-driven treatment, mean +- std over seeds."""
from config import cfg
from tools.sumo import microsim


def run(seeds=None):
    runs = microsim.run_experiment(None, seeds or cfg("sumo")["seeds"])
    s = microsim.summarize(runs)
    s["seeds"] = len(runs["baseline"])
    return s

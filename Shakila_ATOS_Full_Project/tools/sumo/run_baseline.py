"""Baseline run (fixed-time signals, no diversion).  python -m tools.sumo.run_baseline [--seed 1]
Engine: built-in microsim (default). To use real SUMO see docs/sumo_optional.md (tools/sumo/*.xml are the SUMO inputs)."""
import argparse

from tools.sumo.microsim import CorridorSim, default_params

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, default=1); a = ap.parse_args()
    r = CorridorSim(default_params(), False, a.seed).run()
    print({k: round(v, 1) for k, v in r.items() if not isinstance(v, list)})

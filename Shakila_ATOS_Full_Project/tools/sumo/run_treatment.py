"""Treatment run (agent-driven diversion + signal strategy + emergency pre-emption).  python -m tools.sumo.run_treatment"""
import argparse

from tools.sumo.microsim import CorridorSim, default_params

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, default=1); a = ap.parse_args()
    r = CorridorSim(default_params(), True, a.seed).run()
    print({k: round(v, 1) for k, v in r.items() if not isinstance(v, list)})

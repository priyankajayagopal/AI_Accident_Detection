# Simulation report - baseline vs agent-driven clearance (8 seeds, built-in microsimulator)

| Metric | Baseline (fixed-time, no diversion) | With system | Improvement |
|---|---|---|---|
| Emergency-vehicle arrival (s) | 301 +- 5 | 186 +- 2 | 38.2% |
| Queue dissipation after clearance (s) | 48 +- 28 | 21 +- 10 | 56.7% |
| Average delay per vehicle (s) | 138 +- 12 | 69 +- 4 | 49.8% |
| Congestion recovery time (s) | 1563 +- 137 | 516 +- 21 | 67.0% |
| Peak queue (vehicles) | 136 +- 9 | 53 +- 10 | 61.2% |

Assumptions: 5-junction corridor, 400 m spacing, 2 lanes, 2200 veh/h peak inflow, one lane blocked mid-block, blockage cleared 300 s after
first responder arrival, 50% VMS compliance, treatment detection+approval delay 55 s vs 150 s manual report in baseline.
Results are from a calibrated *model*, not field data (see docs/limitations.md).

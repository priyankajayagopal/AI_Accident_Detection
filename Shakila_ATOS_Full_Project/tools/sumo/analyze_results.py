"""Format simulation results as a markdown table."""

LAB = [("emergency_arrival_s", "Emergency-vehicle arrival (s)"), ("queue_dissipation_s", "Queue dissipation after clearance (s)"),
       ("avg_delay_s", "Average delay per vehicle (s)"), ("recovery_s", "Congestion recovery time (s)"), ("max_queue_veh", "Peak queue (vehicles)")]


def to_markdown(s: dict) -> str:
    a = s["aggregate"]
    L = [f"# Simulation report - baseline vs agent-driven clearance ({s.get('seeds', '?')} seeds, built-in microsimulator)", "",
         "| Metric | Baseline (fixed-time, no diversion) | With system | Improvement |", "|---|---|---|---|"]
    for k, lab in LAB:
        L.append(f"| {lab} | {a['baseline'][k]:.0f} +- {a['baseline_std'][k]:.0f} | {a['treatment'][k]:.0f} +- {a['treatment_std'][k]:.0f} | {s['improvement_pct'][k]}% |")
    L += ["", "Assumptions: 5-junction corridor, 400 m spacing, 2 lanes, 2200 veh/h peak inflow, one lane blocked mid-block, blockage cleared 300 s after",
          "first responder arrival, 50% VMS compliance, treatment detection+approval delay 55 s vs 150 s manual report in baseline.",
          "Results are from a calibrated *model*, not field data (see docs/limitations.md)."]
    return "\n".join(L) + "\n"

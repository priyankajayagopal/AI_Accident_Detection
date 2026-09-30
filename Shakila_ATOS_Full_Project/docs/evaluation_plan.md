# Evaluation plan (targets from slide 17)
| Area | Metric | Target | Module |
|---|---|---|---|
| Accident detection | precision, recall, F1, FPR | F1 >= 0.85, FPR < 5% | eval/ablation_harness.py |
| Real time | FPS, latency | >= 15 FPS | eval/detector_benchmark.py |
| Tracking | MOTA, ID switches | MOTA >= 0.70 | eval/tracker_benchmark.py |
| Severity | accuracy, macro-F1 | >= 0.80 | eval/severity_eval.py |
| Clearance (simulation) | ETA, queue dissipation, delay | >= 25% delay reduction | eval/sumo_eval.py |
| System response | detection-to-proposal latency | < 10 s | eval/proposal_eval.py |
| Agents | task success, tool-call accuracy, consistency, fault tolerance | >= 90% | eval/agent_success_eval.py |
| Operator load | acceptance rate, false alarms / hour | - | operator_acceptance_eval, false_alarms_per_hour |
Protocol: video-level 70/15/15 split (no clip leakage), extra held-out test videos, ablation A rules-only -> B low threshold -> C +classifier -> D +VLM.
Run: `python -m scripts.run_evaluation` -> `eval/reports/`.

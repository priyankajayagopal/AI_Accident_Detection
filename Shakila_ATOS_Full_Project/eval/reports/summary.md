# Evaluation summary (synthetic CCTV-style data - see docs/limitations.md)

| Metric | Target | Result | Met |
|---|---|---|---|
| Accident detection F1 (full system) | >= 0.85 | 0.896 | YES |
| False-positive rate (candidate level) | < 0.05 | 0.123 | no |
| Pipeline FPS | >= 15 | 415.3 | YES |
| Tracking MOTA | >= 0.7 | 0.914 | YES |
| Severity macro-F1 | >= 0.8 | 0.968 | YES |
| Delay reduction (simulation) | >= 25% | 49.8% | YES |
| Detection-to-proposal latency (s) | < 10 | 4.7 | YES |
| Agent task success | >= 0.9 | 1.0 | YES |

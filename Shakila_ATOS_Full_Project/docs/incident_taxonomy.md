# Incident taxonomy
| Subtype | Definition | Pipeline behaviour |
|---|---|---|
| accident | contact between vehicles + hard deceleration + vehicles stationary/abnormal afterwards | verified -> operator alert |
| near_miss | hard braking / very small gap without contact | logged for analytics, no alert |
| stopped_vehicle | a vehicle that was moving stops on the carriageway and is not part of a queue | logged (watch-list), no alert |
| congestion_anomaly | >= 6 vehicles slower than 16 km/h for >= 4 s | logged, no alert |
| unknown | classifier cannot decide | operator review if evidence is borderline |

Severity: **low** (single vehicle, no lane blocked) - **medium** (2 vehicles or 1 lane blocked) - **high** (3+ vehicles, pedestrian, heavy vehicle or 2+ lanes blocked)
- **critical** (full blockage, very high impact speed, people/heavy vehicle at speed). Table from slide 10; labels used to train the gradient-boosted model.

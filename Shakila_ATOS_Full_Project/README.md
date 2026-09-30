# AI Accident Detection & Human-in-the-Loop Traffic Clearance (M.Tech project)

**Principle:** *CV sees, agents decide, optimization moves traffic, the LLM only speaks.*
No incident is dispatched without a human operator approval (state machine + guardrail G-rules + hash-chained audit log).

Pipeline: video → detector → tracker → 6-signal candidate engine → evidence package → classifier + VLM verification → severity model → 6 agents (LangGraph orchestrator) → **human approval gate** → dispatch → clearance plan (time-dependent Dijkstra/A*) → microsimulation → report. Dashboard over FastAPI + WebSocket.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.generate_synthetic_data --per-scenario 20 --extra-test 20   # synthetic videos + ground truth (~500 MB)
python -m scripts.train_models          # classifier + severity models
python -m pytest -q                     # 31 tests
python -m scripts.run_evaluation        # writes eval/reports/summary.md
python -m scripts.run_server            # http://localhost:8000  (dashboard + API + /docs)
```
Demo without regenerating everything: `python -m scripts.generate_synthetic_data --demo-only` (3 demo videos used by cameras CAM001–003).

## Demo flow (for the viva)
1. Start server, open http://localhost:8000. Camera CAM001 plays a T-bone crash video.
2. A proposal appears ~1.6 s after impact → verified → severity → status `verified`, waiting for human.
3. Click **Approve** as operator → dispatch (ambulance/police/fire routes), diversion plan, simulation chart (baseline vs treatment), report, audit chain check.
4. `python -m scripts.test_state_machine` shows that auto-dispatch without approval is blocked.

## Results (synthetic data, held-out test videos) — see eval/reports/summary.md
| Metric | Target | Result |
|---|---|---|
| Accident F1 (full system) | ≥0.85 | 0.896 ✔ |
| False-positive rate | <0.05 | 0.123 ✘ (rules-only stage: 0.0) |
| FPS | ≥15 | ~150 ✔ |
| MOTA | ≥0.7 | 0.914 ✔ |
| Severity macro-F1 | ≥0.8 | 0.968 ✔ |
| Delay reduction | ≥25% | 49.8% ✔ |
| Agent task success | ≥0.9 | 1.0 ✔ |

## Honest limitations
Synthetic overhead video (not real CCTV); default VLM is a **mock** (set `VLM_PROVIDER` + key in `.env` for a real one); built-in IDM microsimulator instead of SUMO (docs/sumo_optional.md); dashboard is vanilla JS, not React; YOLO optional (`pip install ultralytics`, set detector backend in configs/detector.yaml). Details in docs/limitations.md.

See `GUIDE_STEP_BY_STEP.md` (2-day plan) and `VIVA_QA.md`.

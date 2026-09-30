# Core scope
**Goal (slide 2):** automate accident detection and coordinate a near-real-time clearance response - camera to cleared road.

**In scope (implemented):** perception (ingestion, detection, tracking, motion features), six-signal candidate engine with temporal evidence,
two-stage verification (classifier + VLM), severity model, six agents + orchestrator + fallback supervisor, human approval gate,
time-dependent routing, corridor simulation (baseline vs treatment), FastAPI + WebSocket backend, control-room dashboard, audit log, evaluation suite.

**Design principle (slide 4):** *CV sees, agents decide, optimization moves traffic, LLM only speaks.* The LLM is never in the real-time path and never
decides severity, verification or routing; it only writes explanations/report summaries (and every decision passes a deterministic guardrail).

**Out of scope (stated boundaries, slide 19):** physical signal actuation (simulation only), city-scale networks, multi-camera fusion, night/rain robustness claims.

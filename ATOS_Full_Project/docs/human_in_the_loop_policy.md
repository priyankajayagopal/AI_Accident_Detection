# Human-in-the-loop policy
1. No dispatch recommendation, clearance plan or simulation exists before `OPERATOR_APPROVED` (state machine + guardrail G5).
2. Only named operators (`configs/app.yaml`) can approve / reject / close; API returns 403 otherwise.
3. Signals are never actuated: every plan is labelled `simulation_only` (guardrail G10) and reports carry an advisory disclaimer (G14).
4. Verified-but-unapproved incidents escalate to a supervisor after 120 s (`safety/escalation.py`, `/api/escalations`).
5. Every transition, guardrail decision and fallback is written to a hash-chained audit log (`/api/audit/verify` proves integrity).

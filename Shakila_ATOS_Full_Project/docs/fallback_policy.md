# Fallback policy - 0 backup LLM agents, 6 deterministic handlers
| Handler | Trigger | Action |
|---|---|---|
| vlm_fallback | VLM timeout / invalid JSON / no key / no keyframes | neutral verdict; verifier re-weights to classifier + rules; flag `fallback_used` |
| classifier_fallback | model missing / exception | accident probability := rule score |
| severity_fallback | model missing / exception | rule table (slide 10) |
| dispatch_fallback | dispatcher error or guardrail block | template services by severity |
| routing_fallback | routing/plan error | precomputed static Route B + standard signal actions |
| report_fallback | report error | plain template report |
Policy: max 1 retry; the fallback output must itself pass the guardrail, else the run halts and a critical alert asks the operator to act manually.
Tested by fault injection: `eval/agent_success_eval.py` (9 fault sets).

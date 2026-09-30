# Agent design
| Component | Role | Tools | Output contract |
|---|---|---|---|
| verifier_agent | classifier + VLM + rule score -> verified / needs_review / rejected | classifier_verify, vlm_verify | VerifierOutput |
| severity_agent | structured features -> gradient-boosted severity | camera_tools.blocked_lanes, workers.severity | SeverityOutput |
| dispatcher_agent | services + priority + ETAs (after approval) | routing_tools.emergency | DispatchPlan |
| traffic_clearance_agent | diversion (Route B), emergency corridor, signal strategy, simulation | routing_tools, sumo_tools | ClearancePlan + SimulationResult |
| reporting_agent | markdown report + audit trail | report_tools | report text |
| guardrail_agent | validates every output before commit (deterministic) | safety.guardrail | GuardrailResult |
| fallback_supervisor (optional) | picks deterministic handler on failure/violation | safety.fallback_handlers | fallback output |
| orchestrator | LangGraph graphs (verification / response), shared state, retry -> guardrail -> fallback | all | AgentContext trace |

Every step: `agent.run()` (pure decision) -> `guardrail.check()` -> `agent.commit()` (state change). One retry, then fallback, then halt + escalate.
LLM use (optional, `ATOS_LLM_BACKEND`): wording of rationales/summaries only. With backend `rule` the whole system is deterministic and offline.

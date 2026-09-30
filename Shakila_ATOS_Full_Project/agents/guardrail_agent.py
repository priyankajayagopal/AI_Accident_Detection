"""Guardrail agent: validates every other agent's output before it is committed. Deterministic (safety/guardrail.py)."""
import time

from agents.agent_state import AgentContext
from safety import audit_logger, guardrail
from safety.escalation import escalate_guardrail_failure
from schemas.agent_outputs import GuardrailResult


class GuardrailAgent:
    name = "guardrail_agent"

    def check(self, ctx: AgentContext, key: str, out: dict) -> GuardrailResult:
        t0 = time.perf_counter()
        if key == "reporting":
            r = guardrail.check_report(out.get("text", ""), ctx.incident)
        else:
            r = guardrail.CHECKS[key](out, ctx.incident)
        ctx.log(self.name, f"check:{key}", ["safety.guardrail"], "pass" if r.passed else "BLOCK",
                {"violations": r.violations, "warnings": r.warnings}, t0)
        if not r.passed:
            e = escalate_guardrail_failure(ctx.incident.incident_id, key, r.violations)
            ctx.alert("warning", e["message"])
        for w in r.warnings:
            ctx.alert("info", w)
        audit_logger.log_event("guardrail", ctx.incident.incident_id, self.name, {"agent": key, "passed": r.passed, "violations": r.violations})
        return r

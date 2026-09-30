"""Escalation: verified incidents waiting too long for an operator, or guardrail failures, go to a supervisor."""
from datetime import datetime, timezone
from typing import List

from config import cfg
from safety import audit_logger
from schemas.incident import IncidentRecord, IncidentStatus


def pending_escalations(incidents: List[IncidentRecord], now: datetime = None) -> List[dict]:
    now = now or datetime.now(timezone.utc)
    limit = cfg("app")["approval"]["escalation_after_seconds"]
    out = []
    for inc in incidents:
        if inc.status == IncidentStatus.VERIFIED and not inc.human_approved:
            waited = (now - inc.updated_at).total_seconds()
            if waited > limit and "escalated" not in inc.flags:
                out.append({"incident_id": inc.incident_id, "waited_s": round(waited),
                            "message": f"Incident {inc.incident_id} unapproved for {round(waited)}s - supervisor attention"})
    return out


def escalate_guardrail_failure(incident_id: str, agent: str, violations: List[str]) -> dict:
    audit_logger.log_event("guardrail_escalation", incident_id, f"agent/{agent}", {"violations": violations})
    return {"incident_id": incident_id, "agent": agent, "violations": violations,
            "message": f"Guardrail blocked {agent} output; operator review required"}

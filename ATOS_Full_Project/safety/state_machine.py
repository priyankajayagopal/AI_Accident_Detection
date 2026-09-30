"""Incident lifecycle state machine - the safety core.

Guarantee: no automated actor can reach OPERATOR_APPROVED (or anything after it) without a human.
Two independent checks:  (1) transition must be in VALID_TRANSITIONS,
                         (2) OPERATOR_APPROVED may only be caused by an actor that starts with "human".
"""
from typing import Callable, Dict, List, Optional

from schemas.incident import IncidentStatus as S

VALID_TRANSITIONS: Dict[Optional[S], List[S]] = {
    None: [S.PROPOSED],
    S.PROPOSED: [S.UNDER_VERIFICATION, S.REJECTED],
    S.UNDER_VERIFICATION: [S.VERIFIED, S.REJECTED],
    S.VERIFIED: [S.OPERATOR_APPROVED, S.REJECTED],
    S.OPERATOR_APPROVED: [S.DISPATCH_RECOMMENDED, S.REJECTED],
    S.DISPATCH_RECOMMENDED: [S.SIMULATED],
    S.SIMULATED: [S.CLOSED],
    S.REJECTED: [S.CLOSED],
    S.CLOSED: [],
}

# transitions only a human operator may trigger
HUMAN_ONLY = {S.OPERATOR_APPROVED}
# a human may also reject at VERIFIED / OPERATOR_APPROVED and close a case
_audit_hook: Optional[Callable[[dict], None]] = None


class InvalidTransitionError(Exception):
    """Raised when an agent or worker tries to make an illegal state change."""


class UnauthorizedActorError(Exception):
    """Raised when a non-human actor tries a human-only transition."""


def set_audit_hook(fn: Optional[Callable[[dict], None]]) -> None:
    global _audit_hook
    _audit_hook = fn


def is_human(actor: str) -> bool:
    return actor.lower().startswith("human")


def validate_transition(current_status: Optional[S], next_status: S, actor: str = "system") -> bool:
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if next_status not in allowed:
        raise InvalidTransitionError(
            f"Illegal state transition: cannot move from '{getattr(current_status, 'value', current_status)}' "
            f"to '{next_status.value}'. Allowed: {[a.value for a in allowed]}. "
            "Human approval is required to proceed past 'verified'."
        )
    if next_status in HUMAN_ONLY and not is_human(actor):
        raise UnauthorizedActorError(
            f"Actor '{actor}' is not a human operator and may not perform transition to '{next_status.value}'."
        )
    return True


def transition_state(current_status: Optional[S], next_status: S, actor: str, note: str = "") -> dict:
    """Validate + audit a transition. Returns the event dict (also sent to the audit hook / DB)."""
    validate_transition(current_status, next_status, actor)
    event = {
        "previous_status": current_status,
        "new_status": next_status,
        "actor": actor,
        "note": note,
    }
    if _audit_hook:
        _audit_hook(event)
    return event

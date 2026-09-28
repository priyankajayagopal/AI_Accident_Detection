from schemas.incident import IncidentStatus
from typing import Tuple

# Define the strict rules of the lifecycle
VALID_TRANSITIONS = {
    None: [IncidentStatus.PROPOSED],
    IncidentStatus.PROPOSED: [IncidentStatus.UNDER_VERIFICATION, IncidentStatus.REJECTED],
    IncidentStatus.UNDER_VERIFICATION: [IncidentStatus.VERIFIED, IncidentStatus.REJECTED],
    IncidentStatus.VERIFIED: [IncidentStatus.OPERATOR_APPROVED, IncidentStatus.REJECTED],
    IncidentStatus.OPERATOR_APPROVED: [IncidentStatus.DISPATCH_RECOMMENDED, IncidentStatus.REJECTED],
    IncidentStatus.DISPATCH_RECOMMENDED: [IncidentStatus.SIMULATED],
    IncidentStatus.SIMULATED: [IncidentStatus.CLOSED],
    IncidentStatus.REJECTED: [IncidentStatus.CLOSED],
}

class InvalidTransitionError(Exception):
    """Raised when an agent or worker tries to make an illegal state change."""
    pass

def validate_transition(current_status: IncidentStatus, next_status: IncidentStatus) -> bool:
    """
    Checks if the proposed state transition is legal according to the HITL policy.
    Crucially, it ensures NO automated system can bypass OPERATOR_APPROVED.
    """
    allowed_next_states = VALID_TRANSITIONS.get(current_status, [])
    
    if next_status not in allowed_next_states:
        raise InvalidTransitionError(
            f"Illegal state transition: Cannot move from '{current_status}' to '{next_status}'. "
            f"Allowed states: {allowed_next_states}. "
            f"Human approval is required to proceed past 'verified'."
        )
    
    return True

def transition_state(current_status: IncidentStatus, next_status: IncidentStatus, actor: str) -> dict:
    """
    Validates and logs the transition. 
    In a real app, this writes to the `incident_events` database table.
    """
    validate_transition(current_status, next_status)
    
    # Audit Log Print (Replace with DB insert later)
    print(f"[AUDIT] Actor: {actor} | Transition: {current_status} -> {next_status}")
    
    return {
        "previous_status": current_status,
        "new_status": next_status,
        "actor": actor
    }
from safety.state_machine import transition_state, InvalidTransitionError
from schemas.incident import IncidentStatus

def test_lifecycle():
    status = IncidentStatus.PROPOSED
    print("Starting Incident Lifecycle Test...\n")

    # 1. CV Pipeline proposes
    status = transition_state(status, IncidentStatus.UNDER_VERIFICATION, actor="pipeline/candidate_engine")["new_status"]
    
    # 2. Classifier verifies
    status = transition_state(status, IncidentStatus.VERIFIED, actor="workers/classifier_verify")["new_status"]
    
    # 3. MALICIOUS ATTEMPT: Agent tries to auto-dispatch without human approval
    try:
        print("\nAttempting illegal auto-dispatch...")
        transition_state(status, IncidentStatus.DISPATCH_RECOMMENDED, actor="agents/dispatcher_agent")
    except InvalidTransitionError as e:
        print(f"BLOCKED! Guardrail caught the error: {e}\n")

    # 4. Human Operator approves
    status = transition_state(status, IncidentStatus.OPERATOR_APPROVED, actor="human_operator_admin")["new_status"]
    
    # 5. Now the agent can recommend dispatch
    status = transition_state(status, IncidentStatus.DISPATCH_RECOMMENDED, actor="agents/dispatcher_agent")["new_status"]
    
    print("\nLifecycle test completed successfully. System is safe.")

if __name__ == "__main__":
    test_lifecycle()
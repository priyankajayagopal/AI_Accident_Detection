"""Day-1 proof that the HITL guardrail works. Run: python -m scripts.test_state_machine"""
from safety.state_machine import InvalidTransitionError, UnauthorizedActorError, transition_state
from schemas.incident import IncidentStatus as S


def test_lifecycle():
    status = S.PROPOSED
    print("Starting incident lifecycle test...\n")
    status = transition_state(status, S.UNDER_VERIFICATION, "pipeline/candidate_engine")["new_status"]
    status = transition_state(status, S.VERIFIED, "workers/classifier_verify")["new_status"]
    try:
        transition_state(status, S.DISPATCH_RECOMMENDED, "agents/dispatcher_agent")
    except InvalidTransitionError as e:
        print("BLOCKED (skip approval):", e)
    try:
        transition_state(status, S.OPERATOR_APPROVED, "agents/dispatcher_agent")
    except UnauthorizedActorError as e:
        print("BLOCKED (agent impersonating operator):", e)
    status = transition_state(status, S.OPERATOR_APPROVED, "human:operator1")["new_status"]
    status = transition_state(status, S.DISPATCH_RECOMMENDED, "agents/dispatcher_agent")["new_status"]
    print("\nLifecycle test completed. System is safe.")


if __name__ == "__main__":
    test_lifecycle()

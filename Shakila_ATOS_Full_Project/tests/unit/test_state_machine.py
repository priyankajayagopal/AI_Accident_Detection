import pytest
from safety.state_machine import InvalidTransitionError, UnauthorizedActorError, transition_state
from schemas.incident import IncidentStatus as S


def test_happy_path():
    s = transition_state(None, S.PROPOSED, "pipeline")["new_status"]
    for nxt, actor in [(S.UNDER_VERIFICATION, "agent"), (S.VERIFIED, "agent"), (S.OPERATOR_APPROVED, "human:op1"),
                       (S.DISPATCH_RECOMMENDED, "agent"), (S.SIMULATED, "agent"), (S.CLOSED, "human:op1")]:
        s = transition_state(s, nxt, actor)["new_status"]
    assert s == S.CLOSED


def test_cannot_skip_human_approval():
    with pytest.raises(InvalidTransitionError):
        transition_state(S.VERIFIED, S.DISPATCH_RECOMMENDED, "agents/dispatcher_agent")


def test_agent_cannot_impersonate_operator():
    with pytest.raises(UnauthorizedActorError):
        transition_state(S.VERIFIED, S.OPERATOR_APPROVED, "agents/dispatcher_agent")


def test_closed_is_terminal():
    with pytest.raises(InvalidTransitionError):
        transition_state(S.CLOSED, S.PROPOSED, "human:x")

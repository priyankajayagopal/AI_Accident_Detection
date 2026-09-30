# Incident state machine (safety/state_machine.py)
```
None -> PROPOSED -> UNDER_VERIFICATION -> VERIFIED -> OPERATOR_APPROVED -> DISPATCH_RECOMMENDED -> SIMULATED -> CLOSED
            \\__________________ REJECTED (from any pre-approval state, or by the operator) -> CLOSED
```
Two independent checks on every change (`transition_state`): (1) the edge must exist in `VALID_TRANSITIONS`; (2) `OPERATOR_APPROVED` may only be caused by an
actor whose id starts with `human`. Therefore an agent cannot skip approval (`InvalidTransitionError`) nor impersonate the operator (`UnauthorizedActorError`).
`apply_transition()` is the only function that changes status; it also writes the DB event and a hash-chained audit entry.
Tests: `tests/unit/test_state_machine.py`, `python -m scripts.test_state_machine`.

from config import cfg
from server.dependencies import get_orchestrator


def check_operator(op: str):
    if op not in cfg("app")["approval"]["operators"]:
        raise PermissionError(f"unknown operator '{op}'")


def approve_and_respond(iid: str, operator: str):
    """Human approval, then the response phase (dispatch -> clearance -> simulation -> report). Worker thread."""
    o = get_orchestrator()
    o.approve(iid, operator)
    o.response_phase(iid)

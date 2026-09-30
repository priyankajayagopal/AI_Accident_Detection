from agents.orchestrator import Orchestrator
from server.repositories import SqlStore
from server.websocket import hub

store = SqlStore()
_orch = None


def get_store() -> SqlStore:
    return store


def get_orchestrator() -> Orchestrator:
    global _orch
    if _orch is None:
        _orch = Orchestrator(store, publisher=hub.publish)
    return _orch

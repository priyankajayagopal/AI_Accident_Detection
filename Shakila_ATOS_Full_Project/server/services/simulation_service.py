from server.dependencies import get_store


def simulation_for(iid: str):
    return get_store().get(iid).simulation

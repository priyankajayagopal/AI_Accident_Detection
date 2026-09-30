from tools import routing


def test_diversion_avoids_blocked_edge():
    p, t = routing.plan_diversion("J2-J3")
    assert ("J2", "J3") not in list(zip(p, p[1:])) and p[0] == "J1" and p[-1] == "J3"


def test_astar_equals_dijkstra():
    assert routing.astar("HOSP", "J4")[0] == routing.dijkstra("HOSP", "J4")[0]


def test_emergency_eta_positive():
    for s in ("ambulance", "police", "fire"):
        assert routing.plan_emergency(s, "J2-J3")[1] > 0

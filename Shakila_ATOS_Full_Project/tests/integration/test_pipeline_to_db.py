from fastapi.testclient import TestClient


def test_api_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'t.db'}")
    import importlib, server.db, server.models, server.repositories, server.dependencies, server.main
    for m in (server.db, server.models, server.repositories, server.dependencies, server.main):
        importlib.reload(m)
    from tests.synthetic.synthetic_incidents import synthetic_candidate
    with TestClient(server.main.app) as c:
        cand, traffic = synthetic_candidate("accident")
        from server.services import incident_service
        iid = incident_service.ingest_candidate(cand, None, traffic)
        assert c.get(f"/api/incidents/{iid}").json()["incident"]["status"] == "verified"
        assert c.post(f"/api/incidents/{iid}/approve", json={"operator": "hacker"}).status_code == 403
        assert c.post(f"/api/incidents/{iid}/approve", json={"operator": "operator1"}).status_code == 200
        d = c.get(f"/api/incidents/{iid}").json()
        assert d["incident"]["status"] == "simulated"
        assert "Advisory" in c.get(f"/api/incidents/{iid}/report").text
        assert c.get("/api/audit/verify").json()["intact"]

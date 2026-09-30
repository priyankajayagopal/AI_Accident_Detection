import asyncio
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from config import all_cameras, path
from safety import audit_logger
from safety.escalation import pending_escalations
from safety.state_machine import InvalidTransitionError
from server.dependencies import get_orchestrator, get_store
from server.services import approval_service, incident_service, report_service
from server.services.video_service import workers
from tools import routing

router = APIRouter(prefix="/api")


class Operator(BaseModel):
    operator: str = "operator1"
    reason: str = "operator rejected"


class Proposal(BaseModel):
    candidate: dict
    evidence_dir: str | None = None
    traffic: dict | None = None


def _inc(iid):
    try:
        return get_store().get(iid)
    except KeyError:
        raise HTTPException(404, "incident not found")


@router.get("/health")
def health():
    return {"status": "ok", "engine": get_orchestrator().engine}


@router.get("/incidents")
def incidents():
    return [i.model_dump(mode="json") for i in get_store().list()]


@router.get("/incidents/{iid}")
def incident(iid: str):
    s = get_store()
    inc = _inc(iid)
    return {"incident": inc.model_dump(mode="json"), "events": s.events(iid), "trace": s.traces(iid)}


@router.post("/incidents/proposals")
def post_proposal(p: Proposal, bg: BackgroundTasks):
    """External pipelines can POST a candidate proposal (the built-in camera workers call the service directly)."""
    bg.add_task(incident_service.ingest_candidate, p.candidate, p.evidence_dir, p.traffic)
    return {"accepted": True}


@router.post("/incidents/{iid}/approve")
def approve(iid: str, op: Operator, bg: BackgroundTasks):
    try:
        approval_service.check_operator(op.operator)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    inc = _inc(iid)
    if inc.status.value != "verified":
        raise HTTPException(409, f"incident is '{inc.status.value}', only 'verified' incidents can be approved")
    bg.add_task(approval_service.approve_and_respond, iid, op.operator)
    return {"accepted": True}


@router.post("/incidents/{iid}/reject")
def reject(iid: str, op: Operator):
    try:
        approval_service.check_operator(op.operator)
        get_orchestrator().reject(iid, op.operator, op.reason)
    except (PermissionError, InvalidTransitionError) as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@router.post("/incidents/{iid}/close")
def close(iid: str, op: Operator):
    try:
        approval_service.check_operator(op.operator)
        get_orchestrator().close(iid, op.operator)
    except (PermissionError, InvalidTransitionError) as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@router.get("/incidents/{iid}/report", response_class=PlainTextResponse)
def report(iid: str):
    t = report_service.report_text(iid)
    if not t:
        raise HTTPException(404, "report not ready")
    return t


@router.get("/incidents/{iid}/evidence/{name}")
def evidence(iid: str, name: str):
    d = _inc(iid).evidence_dir
    f = Path(d or "") / Path(name).name
    if not d or not f.exists():
        raise HTTPException(404)
    return FileResponse(f)


@router.get("/alerts")
def alerts():
    return get_store().alerts()


@router.get("/escalations")
def escalations():
    return pending_escalations(get_store().list())


@router.get("/audit/verify")
def audit_verify():
    ok, n, bad = audit_logger.verify_chain()
    return {"intact": ok, "entries": n, "first_bad_line": bad}


@router.get("/map")
def map_graph():
    return routing.graph_geojson()


@router.get("/cameras")
def cameras():
    out = []
    for c in all_cameras():
        w = workers[c["camera_id"]]
        out.append({"camera_id": c["camera_id"], "name": c["name"], "road_segment": c["road_segment"], "status": w.status, "stats": w.stats})
    return out


@router.post("/cameras/{cam}/start")
def start_camera(cam: str, realtime: bool = True):
    if cam not in workers:
        raise HTTPException(404)
    workers[cam].start(realtime=realtime)
    return {"started": cam}


@router.post("/cameras/{cam}/stop")
def stop_camera(cam: str):
    workers[cam].stop.set()
    return {"stopped": cam}


@router.get("/cameras/{cam}/stream")
def stream(cam: str):
    w = workers.get(cam)
    if w is None:
        raise HTTPException(404)

    async def gen():
        last = None
        while True:
            if w.jpeg is not None and w.jpeg is not last:
                last = w.jpeg
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + last + b"\r\n"
            await asyncio.sleep(0.04)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/metrics/summary")
def summary():
    incs = get_store().list(500)
    by = {}
    for i in incs:
        by[i.status.value] = by.get(i.status.value, 0) + 1
    return {"total": len(incs), "by_status": by}

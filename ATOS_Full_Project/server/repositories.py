"""SQL-backed IncidentStore (SQLite by default, PostgreSQL via DATABASE_URL)."""
import json
from typing import List

from agents.tools.incident_tools import IncidentStore
from schemas.incident import IncidentRecord, utcnow
from server.db import SessionLocal
from server.models import AlertRow, EventRow, IncidentRow, TraceRow


class SqlStore(IncidentStore):
    def get(self, iid):
        with SessionLocal() as s:
            r = s.get(IncidentRow, iid)
            if r is None:
                raise KeyError(iid)
            return IncidentRecord.model_validate_json(r.payload)

    def save(self, inc):
        with SessionLocal() as s:
            r = s.get(IncidentRow, inc.incident_id) or IncidentRow(id=inc.incident_id, created_at=inc.created_at)
            r.camera_id, r.status = inc.location.camera_id, inc.status.value
            r.subtype, r.severity = inc.subtype.value, inc.estimated_severity.level.value
            r.payload, r.updated_at = inc.model_dump_json(), utcnow()
            s.merge(r)
            s.commit()

    def list(self, limit=100) -> List[IncidentRecord]:
        with SessionLocal() as s:
            rows = s.query(IncidentRow).order_by(IncidentRow.created_at.desc()).limit(limit).all()
            return [IncidentRecord.model_validate_json(r.payload) for r in rows]

    def add_event(self, iid, actor, from_status, to_status, note):
        with SessionLocal() as s:
            s.add(EventRow(incident_id=iid, actor=actor, from_status=from_status, to_status=to_status, note=note))
            s.commit()

    def add_trace(self, iid, entry):
        with SessionLocal() as s:
            s.add(TraceRow(incident_id=iid, entry=json.dumps(entry, default=str)))
            s.commit()

    def add_alert(self, iid, level, message):
        with SessionLocal() as s:
            s.add(AlertRow(incident_id=iid, level=level, message=message))
            s.commit()

    def set_payload(self, iid, payload):
        with SessionLocal() as s:
            r = s.get(IncidentRow, iid)
            r.candidate = json.dumps(payload, default=str)
            s.commit()

    def get_payload(self, iid):
        with SessionLocal() as s:
            r = s.get(IncidentRow, iid)
            return json.loads(r.candidate) if r and r.candidate else {}

    def traces(self, iid):
        with SessionLocal() as s:
            return [json.loads(r.entry) for r in s.query(TraceRow).filter_by(incident_id=iid).order_by(TraceRow.id)]

    def events(self, iid):
        with SessionLocal() as s:
            return [{"ts": r.ts.isoformat(), "actor": r.actor, "from": r.from_status, "to": r.to_status, "note": r.note}
                    for r in s.query(EventRow).filter_by(incident_id=iid).order_by(EventRow.id)]

    def alerts(self, limit=50):
        with SessionLocal() as s:
            return [{"incident_id": r.incident_id, "ts": r.ts.isoformat(), "level": r.level, "message": r.message}
                    for r in s.query(AlertRow).order_by(AlertRow.id.desc()).limit(limit)]

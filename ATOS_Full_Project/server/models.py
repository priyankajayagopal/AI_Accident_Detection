from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from server.db import Base


def _now():
    return datetime.now(timezone.utc)


class IncidentRow(Base):
    __tablename__ = "incidents"
    id = Column(String(16), primary_key=True)
    camera_id = Column(String(16), index=True)
    status = Column(String(32), index=True)
    subtype = Column(String(32))
    severity = Column(String(16))
    payload = Column(Text)              # full IncidentRecord JSON
    candidate = Column(Text)            # CV candidate + traffic snapshot JSON
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class EventRow(Base):
    __tablename__ = "incident_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(16), index=True)
    ts = Column(DateTime(timezone=True), default=_now)
    actor = Column(String(64))
    from_status = Column(String(32))
    to_status = Column(String(32))
    note = Column(Text)


class TraceRow(Base):
    __tablename__ = "agent_traces"
    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(16), index=True)
    entry = Column(Text)


class AlertRow(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(16), index=True)
    ts = Column(DateTime(timezone=True), default=_now)
    level = Column(String(16))
    message = Column(Text)

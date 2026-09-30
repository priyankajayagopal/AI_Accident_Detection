"""Append-only, hash-chained audit log (tamper-evident). One JSON object per line."""
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from config import path

_lock = threading.Lock()
_LOG = path("logs", "audit.log")


def _hash(prev: str, body: str) -> str:
    return hashlib.sha256((prev + body).encode()).hexdigest()


def _last_hash(file: Path) -> str:
    if not file.exists() or file.stat().st_size == 0:
        return "GENESIS"
    with open(file, "rb") as f:
        last = f.read().splitlines()[-1]
    try:
        return json.loads(last)["hash"]
    except Exception:
        return "GENESIS"


def log_event(kind: str, incident_id: str, actor: str, detail: dict, file: Path = None) -> dict:
    file = Path(file) if file else _LOG
    file.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        prev = _last_hash(file)
        body = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, "incident_id": incident_id,
                "actor": actor, "detail": detail, "prev": prev}
        body_s = json.dumps(body, sort_keys=True, default=str)
        entry = dict(body, hash=_hash(prev, body_s))
        with open(file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    return entry


def verify_chain(file: Path = None) -> tuple:
    """Returns (ok, n_entries, first_bad_line)."""
    file = Path(file) if file else _LOG
    if not file.exists():
        return True, 0, None
    prev = "GENESIS"
    n = 0
    with open(file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            e = json.loads(line)
            h = e.pop("hash")
            if e["prev"] != prev or _hash(prev, json.dumps(e, sort_keys=True, default=str)) != h:
                return False, n, i
            prev = h
            n += 1
    return True, n, None

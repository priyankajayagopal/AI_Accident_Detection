"""Logs every proposal (accepted or not) for analytics and false-alarm accounting."""
import json
import logging
from datetime import datetime, timezone

from config import path
from schemas.evidence import CandidateProposal

_log = logging.getLogger("atos.pipeline")
if not _log.handlers:
    path("logs").mkdir(exist_ok=True)
    h = logging.FileHandler(path("logs", "pipeline.log"))
    h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _log.addHandler(h)
    _log.setLevel(logging.INFO)


def log_proposal(c: CandidateProposal, outcome: str = "proposed") -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "outcome": outcome, **c.model_dump()}
    _log.info(json.dumps({k: rec[k] for k in ("outcome", "candidate_id", "camera_id", "subtype_hint", "score", "frame_idx")}))
    f = path("data", "processed", "trajectories")
    f.mkdir(parents=True, exist_ok=True)
    with open(f / "proposals.jsonl", "a") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")

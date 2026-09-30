from pathlib import Path
from typing import List


def list_evidence(evidence_dir: str) -> List[str]:
    p = Path(evidence_dir) if evidence_dir else None
    return sorted(x.name for x in p.glob("*")) if p and p.exists() else []


def has_keyframes(evidence_dir: str) -> bool:
    return bool(evidence_dir) and all((Path(evidence_dir) / f"{n}_raw.jpg").exists() for n in ("impact", "after"))

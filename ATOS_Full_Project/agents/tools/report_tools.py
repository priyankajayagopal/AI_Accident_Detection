from pathlib import Path

from config import path


def save_report(incident_id: str, text: str) -> str:
    d = path("storage", "reports")
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"incident_{incident_id}.md"
    f.write_text(text, encoding="utf-8")
    return str(f)

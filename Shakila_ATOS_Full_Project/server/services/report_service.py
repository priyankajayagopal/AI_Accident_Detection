from pathlib import Path

from server.dependencies import get_store


def report_text(iid: str) -> str:
    inc = get_store().get(iid)
    if inc.report_path and Path(inc.report_path).exists():
        return Path(inc.report_path).read_text(encoding="utf-8")
    return ""

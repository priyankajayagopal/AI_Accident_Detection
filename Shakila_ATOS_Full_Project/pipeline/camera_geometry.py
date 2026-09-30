"""Pixel <-> metre conversion and lane geometry for one camera."""
from typing import Dict, List, Tuple

from config import camera as load_camera


class CameraGeometry:
    def __init__(self, camera_id: str):
        self.cfg = load_camera(camera_id)
        self.camera_id = camera_id
        self.ppm = float(self.cfg.get("px_per_meter", 8.0))
        self.fps = float(self.cfg.get("fps", 20))
        self.lanes = self.cfg.get("lanes", [])
        self.capacity = int(self.cfg.get("max_capacity_vehicles", 14))

    def px_to_m(self, px: float) -> float:
        return px / self.ppm

    def m_to_px(self, m: float) -> float:
        return m * self.ppm

    def lanes_blocked(self, bboxes: List[Tuple[float, float, float, float]], min_frac: float = 0.3) -> List[str]:
        """Lane ids where a (stationary) vehicle covers >= min_frac of its own area."""
        blocked = set()
        for (x1, y1, x2, y2) in bboxes:
            area = max(1.0, (x2 - x1) * (y2 - y1))
            horizontal = (x2 - x1) >= (y2 - y1)          # a stopped vehicle blocks the lanes of the road it lies along
            for ln in self.lanes:
                if (ln["dir"] in ("E", "W")) != horizontal:
                    continue
                lx1, ly1, lx2, ly2 = ln["rect"]
                iw = min(x2, lx2) - max(x1, lx1)
                ih = min(y2, ly2) - max(y1, ly1)
                if iw > 0 and ih > 0 and (iw * ih) / area >= min_frac:
                    blocked.add(ln["id"])
        return sorted(blocked)

    def blocked_ratio(self, blocked_ids: List[str]) -> float:
        """Worst-case fraction of lanes blocked within one direction group (1.0 = whole carriageway blocked)."""
        groups: Dict[str, List[str]] = {}
        for ln in self.lanes:
            groups.setdefault(ln["dir"], []).append(ln["id"])
        best = 0.0
        for ids in groups.values():
            best = max(best, len([i for i in ids if i in blocked_ids]) / len(ids))
        return best

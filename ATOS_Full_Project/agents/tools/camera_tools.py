from pipeline.camera_geometry import CameraGeometry
from config import camera as _cam


def get_camera(camera_id: str) -> dict:
    return _cam(camera_id)


def blocked_lanes(camera_id: str, bboxes: list) -> dict:
    g = CameraGeometry(camera_id)
    ids = g.lanes_blocked([tuple(b) for b in bboxes])
    return {"lane_ids": ids, "count": len(ids), "ratio": g.blocked_ratio(ids)}

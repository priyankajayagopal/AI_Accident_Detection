from typing import List, Optional, Tuple
from pydantic import BaseModel


class Lane(BaseModel):
    id: str
    name: str
    dir: str
    rect: Tuple[float, float, float, float]


class CameraConfig(BaseModel):
    camera_id: str
    name: str
    road_segment: str
    junction_id: str
    latitude: float
    longitude: float
    fps: float = 20
    frame_size: Tuple[int, int] = (640, 360)
    px_per_meter: float = 8.0
    lanes: List[Lane] = []
    max_capacity_vehicles: int = 14
    demo_video: Optional[str] = None
    demo_scenario: Optional[str] = None
    source: str = "file"

    class Config:
        extra = "allow"

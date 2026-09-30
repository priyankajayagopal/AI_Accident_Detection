"""PerceptionPipeline: frame -> detections -> tracks -> motion features -> candidate proposals (+ evidence)."""
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from config import cfg
from pipeline.camera_geometry import CameraGeometry
from pipeline.candidate_engine import CandidateEngine
from pipeline.detector import build_detector
from pipeline.evidence_packager import FrameBuffer, package
from pipeline.ingestion import VideoSource
from pipeline.overlay import draw_overlay
from pipeline.track_features import TrackFeatureStore, traffic_state
from pipeline.tracker import ByteTrackLite
from schemas.evidence import CandidateProposal, EvidenceBundle


@dataclass
class FrameResult:
    frame_idx: int
    time_s: float
    tracks: list
    traffic: dict
    candidates: List[CandidateProposal] = field(default_factory=list)
    evidence: List[Optional[EvidenceBundle]] = field(default_factory=list)
    infer_ms: float = 0.0


class PerceptionPipeline:
    def __init__(self, camera_id: str, video_path: Optional[str] = None, detector: Optional[str] = None,
                 save_evidence: bool = True, engine_config: Optional[dict] = None):
        self.geo = CameraGeometry(camera_id)
        self.camera_id = camera_id
        self.detector = build_detector(detector, video_path)
        self.tracker = ByteTrackLite()
        self.store = TrackFeatureStore(self.geo.fps, self.geo.ppm)
        self.engine = CandidateEngine(self.geo, engine_config)
        self.buffer = FrameBuffer(7.0, self.geo.fps)
        self.save_evidence = save_evidence
        self.active_ids: set = set()
        self.banner: Optional[str] = None
        self.latencies: List[float] = []

    def process(self, idx: int, frame) -> FrameResult:
        t0 = time.perf_counter()
        self.buffer.push(idx, frame)
        dets = self.detector.detect(frame)
        tracks = self.tracker.update(dets, idx)
        self.store.update(idx, tracks)
        cands = self.engine.update(idx, tracks, self.store)
        ev = []
        for c in cands:
            ev.append(package(c, self.buffer, self.store, self.geo.fps) if self.save_evidence else None)
            if c.subtype_hint == "accident":
                self.active_ids |= set(c.track_ids)
                self.banner = f"ACCIDENT SUSPECTED - proposal {c.candidate_id} (score {c.score:.2f})"
        dt = (time.perf_counter() - t0) * 1000
        self.latencies.append(dt)
        tr = traffic_state(self.store, tracks, idx, self.geo.capacity)
        return FrameResult(idx, idx / self.geo.fps, tracks, tr, cands, ev, dt)

    def annotate(self, frame, res: FrameResult):
        fps = 1000.0 / max(1e-3, sum(self.latencies[-20:]) / len(self.latencies[-20:])) if self.latencies else 0
        stats = f"{self.camera_id}  t={res.time_s:5.1f}s  veh={res.traffic['vehicle_count']}  avg={res.traffic['avg_speed_kmh']}km/h  {fps:4.0f} FPS"
        return draw_overlay(frame, res.tracks, self.store, res.frame_idx, self.active_ids, self.banner, stats)

    def run_video(self, path: str, on_candidate: Optional[Callable] = None, on_frame: Optional[Callable] = None,
                  realtime: bool = False, max_frames: Optional[int] = None) -> List[CandidateProposal]:
        src = VideoSource(path, realtime=realtime)
        out = []
        try:
            for idx, ts, frame in src.frames():
                res = self.process(idx, frame)
                if on_frame:
                    on_frame(frame, res)
                for c, ev in zip(res.candidates, res.evidence):
                    out.append(c)
                    if on_candidate:
                        on_candidate(c, ev)
                if max_frames and idx + 1 >= max_frames:
                    break
        finally:
            src.release()
        return out

    def fps(self) -> float:
        if not self.latencies:
            return 0.0
        return 1000.0 / (sum(self.latencies) / len(self.latencies))

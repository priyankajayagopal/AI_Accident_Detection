from pipeline.camera_geometry import CameraGeometry
from pipeline.candidate_engine import CandidateEngine, overlap_ratio, rect_gap_px
from pipeline.track_features import TrackFeatureStore
from pipeline.tracker import Track


def test_geometry_helpers():
    assert overlap_ratio((0, 0, 10, 10), (5, 0, 15, 10)) == 0.5
    assert rect_gap_px((0, 0, 10, 10), (13, 0, 20, 10)) == 3


def _drive(engine, store, crash):
    """Two synthetic tracks: one moving right, one moving down, meeting at (300,200)."""
    out = []
    for f in range(160):
        a_x = 100 + 5 * f if not (crash and f > 40) else 100 + 5 * 40
        b_y = 100 + 3 * f if not (crash and f > 40) else 100 + 3 * 40
        if not crash:
            b_y = 100 + 3 * f
            a_x = 100 + 5 * f - 400   # far apart
        ta = Track(1, (a_x, 194, a_x + 36, 212), "car", 0.9, hits=5, confirmed=True)
        tb = Track(2, (215, b_y, 233, b_y + 36), "car", 0.9, hits=5, confirmed=True)
        store.update(f, [ta, tb])
        out += engine.update(f, [ta, tb], store)
    return out


def test_crash_is_proposed_and_free_flow_is_not():
    g = CameraGeometry("CAM001")
    e1, s1 = CandidateEngine(g), TrackFeatureStore(g.fps, g.ppm)
    e2, s2 = CandidateEngine(g), TrackFeatureStore(g.fps, g.ppm)
    assert any(c.subtype_hint == "accident" for c in _drive(e1, s1, True))
    assert not _drive(e2, s2, False)

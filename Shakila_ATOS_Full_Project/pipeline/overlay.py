"""Draw detections, tracks and incident banners on a frame (Live Video panel)."""
import cv2


def draw_overlay(frame, tracks, store, f, active_ids=(), banner=None, stats=None):
    img = frame.copy()
    for t in tracks:
        x1, y1, x2, y2 = [int(v) for v in t.bbox]
        hot = t.id in active_ids
        col = (40, 40, 240) if hot else (60, 220, 60)
        cv2.rectangle(img, (x1, y1), (x2, y2), col, 2 if not hot else 3)
        s = store.get(t.id, f)
        kmh = int(round((s["speed"] if s else 0) * 3.6))
        cv2.putText(img, f"#{t.id} {kmh}km/h", (x1, max(10, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1, cv2.LINE_AA)
    if banner:
        cv2.rectangle(img, (0, 0), (img.shape[1], 24), (30, 30, 200), -1)
        cv2.putText(img, banner, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    if stats:
        cv2.putText(img, stats, (8, img.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
    return img

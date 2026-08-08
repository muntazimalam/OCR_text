import cv2
import numpy as np
from app.analyzers.duplicate import DuplicateAnalyzer


def create_sample_img_bytes(val: int = 100) -> bytes:
    img = np.full((100, 100, 3), val, dtype=np.uint8)
    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


def test_phash_computation():
    bytes_a = create_sample_img_bytes(100)
    analyzer = DuplicateAnalyzer()
    res = analyzer.analyze("dummy.jpg", bytes_a)

    assert "phash" in res
    assert len(res["phash"]) > 0
    assert res["is_duplicate"] is False

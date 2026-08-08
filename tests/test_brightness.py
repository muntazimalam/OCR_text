import cv2
import numpy as np
from app.analyzers.brightness import BrightnessAnalyzer


def create_solid_image_bytes(val: int) -> bytes:
    img = np.full((100, 100, 3), val, dtype=np.uint8)
    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


def test_very_dark_brightness():
    bytes_data = create_solid_image_bytes(20)
    analyzer = BrightnessAnalyzer()
    res = analyzer.analyze("dummy.jpg", bytes_data)

    assert res["status"] == "very_dark"
    assert res["score"] < 40


def test_acceptable_brightness():
    bytes_data = create_solid_image_bytes(120)
    analyzer = BrightnessAnalyzer()
    res = analyzer.analyze("dummy.jpg", bytes_data)

    assert res["status"] == "acceptable"
    assert 80 <= res["score"] <= 180


def test_overexposed_brightness():
    bytes_data = create_solid_image_bytes(240)
    analyzer = BrightnessAnalyzer()
    res = analyzer.analyze("dummy.jpg", bytes_data)

    assert res["status"] == "overexposed"
    assert res["score"] > 220

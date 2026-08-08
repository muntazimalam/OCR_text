import io
import cv2
import numpy as np
from PIL import Image as PILImage
from app.analyzers.blur import BlurAnalyzer


def create_test_image_bytes(blur: bool = False) -> bytes:
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    if not blur:
        cv2.rectangle(img, (20, 20), (180, 180), (255, 255, 255), 5)
        cv2.line(img, (0, 0), (200, 200), (255, 255, 255), 3)
    else:
        cv2.rectangle(img, (20, 20), (180, 180), (255, 255, 255), 5)
        img = cv2.GaussianBlur(img, (21, 21), 0)

    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


def test_sharp_image_blur_score():
    sharp_bytes = create_test_image_bytes(blur=False)
    analyzer = BlurAnalyzer()
    res = analyzer.analyze("dummy.jpg", sharp_bytes)

    assert "score" in res
    assert res["is_blurry"] is False
    assert res["score"] >= 100.0


def test_blurry_image_blur_score():
    blurry_bytes = create_test_image_bytes(blur=True)
    analyzer = BlurAnalyzer()
    res = analyzer.analyze("dummy.jpg", blurry_bytes)

    assert "score" in res
    assert res["is_blurry"] is True
    assert res["score"] < 100.0

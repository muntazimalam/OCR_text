import io
import cv2
import numpy as np
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def create_test_jpeg():
    img = np.full((100, 100, 3), 150, dtype=np.uint8)
    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Media Processing Pipeline" in response.text

    info_resp = client.get("/api/info")
    assert info_resp.status_code == 200
    assert info_resp.json()["status"] == "running"


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "healthy"


def test_invalid_file_type_upload():
    response = client.post(
        "/api/v1/images",
        files={"file": ("test.txt", b"Hello world text file", "text/plain")}
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_valid_image_upload_returns_pending():
    img_bytes = create_test_jpeg()
    response = client.post(
        "/api/v1/images",
        files={"file": ("sample.jpg", img_bytes, "image/jpeg")}
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] in ["pending", "processing", "completed"]


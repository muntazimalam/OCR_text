import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_status_non_existent_image():
    random_id = uuid.uuid4()
    response = client.get(f"/api/v1/images/{random_id}/status")
    assert response.status_code == 404
    assert f"Image with ID '{random_id}' not found" in response.json()["detail"]


def test_results_non_existent_image():
    random_id = uuid.uuid4()
    response = client.get(f"/api/v1/images/{random_id}/results")
    assert response.status_code == 404
    assert f"Image with ID '{random_id}' not found" in response.json()["detail"]

import io
import cv2
import numpy as np
import time
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
import app.analyzers.ocr as ocr_module


def create_vehicle_image_with_plate():
    img = np.full((300, 400, 3), 150, dtype=np.uint8)
    cv2.rectangle(img, (50, 100), (350, 250), (50, 50, 200), -1)
    cv2.rectangle(img, (120, 180), (280, 220), (255, 255, 255), -1)
    cv2.putText(img, "KA01AB1234", (130, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


def test_e2e_image_processing_pipeline():
    mock_reader = MagicMock()
    mock_reader.readtext.return_value = [([], "KA01AB1234", 0.95)]
    ocr_module._easyocr_reader = mock_reader
    img_bytes = create_vehicle_image_with_plate()

    with TestClient(fastapi_app) as client:
        t0 = time.time()
        print(f"[{time.time()-t0:.2f}s] STEP 1: Uploading image...")
        response = client.post(
            "/api/v1/images",
            files={"file": ("test_car.jpg", img_bytes, "image/jpeg")}
        )
        print(f"[{time.time()-t0:.2f}s] STEP 1 DONE.")
        assert response.status_code == 201
        upload_data = response.json()
        image_id = upload_data["id"]
        assert upload_data["status"] in ["pending", "completed"]

        print(f"[{time.time()-t0:.2f}s] STEP 2: Checking status...")
        status_resp = client.get(f"/api/v1/images/{image_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["id"] == image_id

        print(f"[{time.time()-t0:.2f}s] STEP 3: Checking results...")
        results_resp = client.get(f"/api/v1/images/{image_id}/results")
        assert results_resp.status_code == 200
        res_data = results_resp.json()
        assert res_data["image_id"] == image_id
        assert res_data["analysis"] is not None
        assert "blur" in res_data["analysis"]
        assert "brightness" in res_data["analysis"]

        print(f"[{time.time()-t0:.2f}s] STEP 4: Serving file...")
        file_resp = client.get(f"/api/v1/images/{image_id}/file")
        assert file_resp.status_code == 200
        assert file_resp.headers["content-type"] == "image/jpeg"

        print(f"[{time.time()-t0:.2f}s] STEP 5: Listing images...")
        list_resp = client.get("/api/v1/images")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] >= 1
        assert any(item["id"] == image_id for item in list_data["items"])

        print(f"[{time.time()-t0:.2f}s] STEP 6: Deleting image...")
        del_resp = client.delete(f"/api/v1/images/{image_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        print(f"[{time.time()-t0:.2f}s] STEP 7: Verifying 404 after delete...")
        status_after_del = client.get(f"/api/v1/images/{image_id}/status")
        assert status_after_del.status_code == 404
        print(f"[{time.time()-t0:.2f}s] ALL STEPS COMPLETED!")

import time
from fastapi.testclient import TestClient

from tests.conftest import TestingSessionLocal
from app.main import app
from app.models.visit import VisitorVisit

client = TestClient(app)


def _visit_count() -> int:
    db = TestingSessionLocal()
    try:
        return db.query(VisitorVisit).count()
    finally:
        db.close()


def _latest_visit():
    db = TestingSessionLocal()
    try:
        return db.query(VisitorVisit).order_by(VisitorVisit.accessed_at.desc()).first()
    finally:
        db.close()


def test_dashboard_page_visit_recorded():
    before = _visit_count()
    response = client.get("/")
    assert response.status_code == 200

    # The insert is synchronous inside the middleware, so the row must exist now.
    visit = _latest_visit()
    assert _visit_count() == before + 1
    assert visit is not None
    assert visit.ip_address  # e.g. "testclient" / 127.0.0.1
    assert visit.path == "/"
    assert visit.accessed_at is not None


def test_non_page_endpoints_not_recorded_as_visits():
    before = _visit_count()
    client.get("/api/info")
    client.get("/api/v1/health")
    client.get("/static/css/style.css")
    assert _visit_count() == before


def test_visits_list_endpoint():
    client.get("/")
    response = client.get("/api/v1/visits?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["items"]
    assert data["items"][0]["path"] == "/"
    assert "accessed_at" in data["items"][0]
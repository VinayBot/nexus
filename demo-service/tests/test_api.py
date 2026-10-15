from fastapi.testclient import TestClient

from app.main import app


def test_create_guest_order():
    with TestClient(app) as client:
        r = client.post("/orders", json={"items": [{"price": 5, "qty": 1}], "email": None})
        assert r.status_code == 200
        assert r.json()["customer"]["guest"] is True


def test_health_endpoint():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] in {"healthy", "degraded", "down"}

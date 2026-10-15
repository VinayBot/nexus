from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_and_get():
    r = client.post("/items", json={"name": "tea", "price": 6.5})
    assert r.status_code == 201
    item_id = r.json()["id"]
    assert client.get(f"/items/{item_id}").json()["name"] == "tea"


def test_validation():
    assert client.post("/items", json={"name": "", "price": -1}).status_code == 422


def test_missing_is_404():
    assert client.get("/items/9999").status_code == 404

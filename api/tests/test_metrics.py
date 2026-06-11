import pytest


@pytest.fixture(autouse=True, scope="module")
def seed_device(client):
    client.post("/devices", json={"hostname": "METRIC-SW", "ip_address": "10.99.0.1", "site": "HQ"})


def test_ingest_metric(client):
    payload = {"device_id": 1, "status": "up", "cpu_percent": 42.5, "memory_percent": 61.0}
    response = client.post("/metrics", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "up"
    assert data["cpu_percent"] == 42.5


def test_ingest_metric_unknown_device(client):
    payload = {"device_id": 999, "status": "up"}
    response = client.post("/metrics", json=payload)
    assert response.status_code == 404


def test_ingest_invalid_status(client):
    payload = {"device_id": 1, "status": "broken"}
    response = client.post("/metrics", json=payload)
    assert response.status_code == 422


def test_get_device_metrics(client):
    response = client.get("/devices/1/metrics")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_latest_metrics(client):
    response = client.get("/metrics/latest")
    assert response.status_code == 200
    assert any(m["device_id"] == 1 for m in response.json())

def test_ingest_metric(client, create_device, auth_headers):
    device = create_device()
    payload = {
        "device_id": device["id"],
        "status": "up",
        "cpu_percent": 42.5,
        "memory_percent": 61.0,
    }
    response = client.post("/v1/metrics", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "up"
    assert data["cpu_percent"] == 42.5
    assert "raw_output" not in data  # deliberately excluded from responses


def test_ingest_metric_unknown_device(client, auth_headers):
    response = client.post(
        "/v1/metrics", json={"device_id": 999, "status": "up"}, headers=auth_headers
    )
    assert response.status_code == 404


def test_ingest_invalid_status(client, create_device, auth_headers):
    device = create_device()
    response = client.post(
        "/v1/metrics", json={"device_id": device["id"], "status": "broken"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_ingest_oversized_raw_output_rejected(client, create_device, auth_headers):
    """raw_output beyond the schema cap must 422, not bloat the row (FM-A5)."""
    device = create_device()
    response = client.post(
        "/v1/metrics",
        json={"device_id": device["id"], "status": "up", "raw_output": "x" * 10_001},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_get_device_metrics_newest_first(client, create_device, auth_headers):
    device = create_device()
    for cpu in (10, 20):
        client.post(
            "/v1/metrics",
            json={"device_id": device["id"], "status": "up", "cpu_percent": cpu},
            headers=auth_headers,
        )
    response = client.get(f"/v1/devices/{device['id']}/metrics")
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert page["items"][0]["id"] > page["items"][1]["id"]  # newest first


def test_get_latest_metrics_one_row_per_device(client, create_device, auth_headers):
    dev_a = create_device(hostname="SW-A", ip_address="10.0.0.1")
    dev_b = create_device(hostname="SW-B", ip_address="10.0.0.2")
    for device in (dev_a, dev_b):
        for state in ("up", "down"):
            client.post(
                "/v1/metrics",
                json={"device_id": device["id"], "status": state},
                headers=auth_headers,
            )

    response = client.get("/v1/metrics/latest")
    assert response.status_code == 200
    latest = response.json()["items"]
    assert {m["device_id"] for m in latest} == {dev_a["id"], dev_b["id"]}
    assert all(m["status"] == "down" for m in latest)  # the newer row won


def test_latest_metrics_breaks_timestamp_ties(client, create_device, test_db):
    """Two metrics sharing a collected_at must still yield exactly one row (FM-E6).

    A max(collected_at) join returns both; ranking with an id tiebreak wins.
    """
    from datetime import UTC, datetime

    from app.models.metric import Metric

    device = create_device()
    same_instant = datetime.now(UTC)
    with test_db.session_factory() as db:
        db.add(Metric(device_id=device["id"], status="up", collected_at=same_instant))
        db.add(Metric(device_id=device["id"], status="down", collected_at=same_instant))
        db.commit()

    latest = client.get("/v1/metrics/latest").json()["items"]
    assert len(latest) == 1
    assert latest[0]["status"] == "down"  # the higher id wins the tie


def test_latest_metrics_omits_devices_without_data(client, create_device):
    """Contract: devices with no metrics are absent, not present-with-nulls."""
    create_device()
    response = client.get("/v1/metrics/latest")
    assert response.status_code == 200
    assert response.json()["items"] == []

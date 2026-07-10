def test_ingest_metric(client, create_device, auth_headers):
    device = create_device()
    payload = {
        "device_id": device["id"],
        "status": "up",
        "cpu_percent": 42.5,
        "memory_percent": 61.0,
    }
    response = client.post("/metrics", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "up"
    assert data["cpu_percent"] == 42.5
    assert "raw_output" not in data  # deliberately excluded from responses


def test_ingest_metric_unknown_device(client, auth_headers):
    response = client.post(
        "/metrics", json={"device_id": 999, "status": "up"}, headers=auth_headers
    )
    assert response.status_code == 404


def test_ingest_invalid_status(client, create_device, auth_headers):
    device = create_device()
    response = client.post(
        "/metrics", json={"device_id": device["id"], "status": "broken"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_ingest_oversized_raw_output_rejected(client, create_device, auth_headers):
    """raw_output beyond the schema cap must 422, not bloat the row (FM-A5)."""
    device = create_device()
    response = client.post(
        "/metrics",
        json={"device_id": device["id"], "status": "up", "raw_output": "x" * 10_001},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_get_device_metrics_newest_first(client, create_device, auth_headers):
    device = create_device()
    for cpu in (10, 20):
        client.post(
            "/metrics",
            json={"device_id": device["id"], "status": "up", "cpu_percent": cpu},
            headers=auth_headers,
        )
    response = client.get(f"/devices/{device['id']}/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert len(metrics) == 2
    assert metrics[0]["id"] > metrics[1]["id"]  # newest first


def test_get_latest_metrics_one_row_per_device(client, create_device, auth_headers):
    dev_a = create_device(hostname="SW-A", ip_address="10.0.0.1")
    dev_b = create_device(hostname="SW-B", ip_address="10.0.0.2")
    for device in (dev_a, dev_b):
        for state in ("up", "down"):
            client.post(
                "/metrics",
                json={"device_id": device["id"], "status": state},
                headers=auth_headers,
            )

    response = client.get("/metrics/latest")
    assert response.status_code == 200
    latest = response.json()
    assert {m["device_id"] for m in latest} == {dev_a["id"], dev_b["id"]}
    assert all(m["status"] == "down" for m in latest)  # the newer row won


def test_latest_metrics_omits_devices_without_data(client, create_device):
    """Contract: devices with no metrics are absent, not present-with-nulls."""
    create_device()
    response = client.get("/metrics/latest")
    assert response.status_code == 200
    assert response.json() == []

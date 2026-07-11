HEARTBEAT = {
    "name": "poller",
    "devices_polled": 5,
    "failures": 1,
    "cycle_seconds": 12.5,
    "interval_seconds": 60,
}


def test_heartbeat_requires_key(client):
    assert client.post("/poller/heartbeat", json=HEARTBEAT).status_code == 401


def test_heartbeat_requires_metrics_write_scope(client, make_api_key):
    raw_key = make_api_key(name="devices-only", scopes="devices:write")
    resp = client.post("/poller/heartbeat", json=HEARTBEAT, headers={"X-API-Key": raw_key})
    assert resp.status_code == 403


def test_heartbeat_creates_status_row(client, auth_headers):
    resp = client.post("/poller/heartbeat", json=HEARTBEAT, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "poller"
    assert data["devices_polled"] == 5
    assert data["last_seen_at"] is not None

    status = client.get("/poller/status")
    assert status.status_code == 200
    assert len(status.json()) == 1


def test_heartbeat_upserts_single_row(client, auth_headers):
    client.post("/poller/heartbeat", json=HEARTBEAT, headers=auth_headers)
    first = client.get("/poller/status").json()[0]

    updated = {**HEARTBEAT, "devices_polled": 9, "failures": 0}
    client.post("/poller/heartbeat", json=updated, headers=auth_headers)

    rows = client.get("/poller/status").json()
    assert len(rows) == 1
    assert rows[0]["devices_polled"] == 9
    assert rows[0]["last_seen_at"] >= first["last_seen_at"]


def test_heartbeat_rejects_negative_counts(client, auth_headers):
    bad = {**HEARTBEAT, "devices_polled": -1}
    resp = client.post("/poller/heartbeat", json=bad, headers=auth_headers)
    assert resp.status_code == 422


def test_status_read_is_open(client):
    assert client.get("/poller/status").status_code == 200

"""Contract tests for API-key auth: who can do what, and what they see when they can't.

401 = unknown identity (no key, bad key, revoked key)
403 = known identity, insufficient scope
Reads stay open until human auth lands in Phase 6.
"""

DEVICE = {"hostname": "SW-01", "ip_address": "10.0.0.1", "site": "HQ"}


def test_write_without_key_returns_401(client):
    assert client.post("/devices", json=DEVICE).status_code == 401


def test_write_with_bogus_key_returns_401(client):
    resp = client.post("/devices", json=DEVICE, headers={"X-API-Key": "nwk_not-a-real-key"})
    assert resp.status_code == 401


def test_revoked_key_returns_401(client, make_api_key):
    raw_key = make_api_key(name="revoked-service", is_active=False)
    resp = client.post("/devices", json=DEVICE, headers={"X-API-Key": raw_key})
    assert resp.status_code == 401


def test_key_without_scope_returns_403(client, make_api_key):
    """A valid identity with the wrong scope is 'forbidden', not 'who are you'."""
    raw_key = make_api_key(name="metrics-only", scopes="metrics:write")
    resp = client.post("/devices", json=DEVICE, headers={"X-API-Key": raw_key})
    assert resp.status_code == 403
    assert "devices:write" in resp.json()["detail"]


def test_scoped_key_can_do_its_job(client, make_api_key, create_device):
    """The poller's real shape: metrics:write lets it ingest, nothing else."""
    device = create_device()
    poller_key = make_api_key(name="poller", scopes="metrics:write")
    headers = {"X-API-Key": poller_key}

    ingest = client.post(
        "/metrics", json={"device_id": device["id"], "status": "up"}, headers=headers
    )
    assert ingest.status_code == 201

    assert client.delete(f"/devices/{device['id']}", headers=headers).status_code == 403


def test_patch_and_delete_require_key(client, create_device):
    device = create_device()
    assert client.patch(f"/devices/{device['id']}", json={"site": "B"}).status_code == 401
    assert client.delete(f"/devices/{device['id']}").status_code == 401


def test_reads_stay_open(client, create_device):
    """The dashboard has no identity until Phase 6 — GETs must work keyless."""
    device = create_device()
    assert client.get("/devices").status_code == 200
    assert client.get(f"/devices/{device['id']}").status_code == 200
    assert client.get("/metrics/latest").status_code == 200
    assert client.get(f"/devices/{device['id']}/metrics").status_code == 200

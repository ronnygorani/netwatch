"""Phase 3 wrap-up: versioning, validation, rate limiting, retention."""

from datetime import UTC, datetime, timedelta

from app.config import settings
from app.models.metric import Metric

HEARTBEAT = {
    "name": "poller",
    "devices_polled": 1,
    "failures": 0,
    "cycle_seconds": 1.0,
    "interval_seconds": 60,
}


def test_legacy_paths_redirect_to_v1(client, create_device):
    device = create_device()
    resp = client.get(f"/devices/{device['id']}", follow_redirects=False)
    assert resp.status_code == 308
    assert resp.headers["location"].endswith(f"/v1/devices/{device['id']}")
    # 308 preserves method and body, so old clients keep working end to end.
    assert client.get(f"/devices/{device['id']}").status_code == 200


def test_health_stays_unversioned(client):
    assert client.get("/health", follow_redirects=False).status_code in (200, 503)


def test_unknown_device_type_rejected(client, auth_headers):
    """device_type must be a platform the poller can speak (FM-E8)."""
    resp = client.post(
        "/v1/devices",
        json={"hostname": "SW-X", "ip_address": "10.0.0.5", "site": "HQ", "device_type": "cisco"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_arista_device_type_accepted(create_device):
    device = create_device(device_type="arista_eos", ip_address="10.0.0.6")
    assert device["device_type"] == "arista_eos"


def test_rate_limit_returns_429(client, make_api_key, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    headers = {"X-API-Key": make_api_key(name="limited")}
    payload = {"device_id": 999, "status": "up"}  # 404s, but still counts

    statuses = [
        client.post("/v1/metrics", json=payload, headers=headers).status_code for _ in range(4)
    ]
    assert statuses[:3] == [404, 404, 404]
    assert statuses[3] == 429


def test_old_metrics_purged_on_heartbeat(client, create_device, auth_headers, test_db):
    device = create_device()
    client.post(
        "/v1/metrics", json={"device_id": device["id"], "status": "up"}, headers=auth_headers
    )
    # Backdate a second metric past the retention window (server sets
    # collected_at on ingest, so old rows must be planted directly).
    with test_db.session_factory() as db:
        db.add(
            Metric(
                device_id=device["id"],
                status="up",
                collected_at=datetime.now(UTC) - timedelta(days=settings.metric_retention_days + 1),
            )
        )
        db.commit()

    assert client.get(f"/v1/devices/{device['id']}/metrics").json()["total"] == 2
    client.post("/v1/poller/heartbeat", json=HEARTBEAT, headers=auth_headers)
    assert client.get(f"/v1/devices/{device['id']}/metrics").json()["total"] == 1

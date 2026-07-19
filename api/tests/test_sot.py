"""Source-of-truth sync: mapping, cache reconciliation, and the endpoint."""

from app import nautobot
from app.models.device import Device
from app.nautobot import map_nautobot_device, sync_devices

NB_DEVICE = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "name": "spine1",
    "platform": {"network_driver": "arista_eos"},
    "primary_ip4": {"address": "172.20.20.11/24"},
    "location": {"name": "LAB"},
    "status": {"name": "Active"},
}


def test_map_full_device():
    assert map_nautobot_device(NB_DEVICE) == {
        "nautobot_id": NB_DEVICE["id"],
        "hostname": "spine1",
        "ip_address": "172.20.20.11",
        "site": "LAB",
        "device_type": "arista_eos",
        "is_active": True,
    }


def test_map_skips_device_without_primary_ip():
    assert map_nautobot_device({**NB_DEVICE, "primary_ip4": None}) is None


def test_map_skips_unsupported_driver():
    bad = {**NB_DEVICE, "platform": {"network_driver": "vyos"}}
    assert map_nautobot_device(bad) is None


def test_map_inactive_status():
    offline = {**NB_DEVICE, "status": {"name": "Decommissioning"}}
    assert map_nautobot_device(offline)["is_active"] is False


def _mapped(**overrides):
    return {**map_nautobot_device(NB_DEVICE), **overrides}


def test_sync_creates_updates_and_deactivates(test_db):
    with test_db.session_factory() as db:
        assert sync_devices(db, [_mapped()]) == {
            "created": 1,
            "updated": 0,
            "deactivated": 0,
        }
        # Same data again: idempotent.
        assert sync_devices(db, [_mapped()])["created"] == 0
        # Changed hostname in the SoT wins.
        counts = sync_devices(db, [_mapped(hostname="spine1-renamed")])
        assert counts["updated"] == 1
        assert db.query(Device).one().hostname == "spine1-renamed"
        # Vanished from the SoT: deactivated, not deleted (history survives).
        counts = sync_devices(db, [])
        assert counts["deactivated"] == 1
        assert db.query(Device).one().is_active is False


def test_sync_adopts_existing_row_by_ip(client, create_device, test_db):
    local = create_device(hostname="spine1", ip_address="172.20.20.11")
    with test_db.session_factory() as db:
        counts = sync_devices(db, [_mapped()])
        assert counts == {"created": 0, "updated": 1, "deactivated": 0}
        row = db.query(Device).one()
        assert row.id == local["id"]
        assert row.nautobot_id == NB_DEVICE["id"]


def test_sync_leaves_local_devices_alone(client, create_device, test_db):
    create_device(hostname="manual-demo", ip_address="192.0.2.1")
    with test_db.session_factory() as db:
        counts = sync_devices(db, [])
        assert counts["deactivated"] == 0


def test_sync_endpoint_requires_scope(client, make_api_key):
    key = make_api_key(name="poller-old", scopes="metrics:write")
    resp = client.post("/v1/sot/sync", headers={"X-API-Key": key})
    assert resp.status_code == 403


def test_sync_endpoint_unconfigured_returns_503(client, make_api_key, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nautobot_token", "")
    key = make_api_key(name="syncer", scopes="sot:sync")
    resp = client.post("/v1/sot/sync", headers={"X-API-Key": key})
    assert resp.status_code == 503


def test_sync_endpoint_end_to_end(client, make_api_key, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nautobot_token", "test-token")
    monkeypatch.setattr(nautobot, "fetch_nautobot_devices", lambda: [NB_DEVICE])
    # The router imported the symbol directly; patch it there too.
    from app.routers import sot

    monkeypatch.setattr(sot, "fetch_nautobot_devices", lambda: [NB_DEVICE])

    key = make_api_key(name="syncer", scopes="sot:sync")
    resp = client.post("/v1/sot/sync", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "updated": 0, "deactivated": 0, "skipped": 0}

    devices = client.get("/v1/devices").json()["items"]
    assert devices[0]["nautobot_id"] == NB_DEVICE["id"]

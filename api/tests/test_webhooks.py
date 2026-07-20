"""Nautobot webhook receiver: HMAC verification and sync triggering."""

import hashlib
import hmac
import json

from app import nautobot
from app.config import settings

SECRET = "test-webhook-secret"
EVENT = {"event": "created", "model": "device", "data": {"name": "leaf3"}}

NB_DEVICE = {
    "id": "bbbbbbbb-0000-0000-0000-000000000002",
    "name": "leaf3",
    "platform": {"network_driver": "arista_eos"},
    "primary_ip4": {"address": "172.20.20.14/24"},
    "location": {"name": "LAB"},
    "status": {"name": "Active"},
}


def signed(body: bytes) -> dict:
    signature = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
    return {"X-Hook-Signature": signature, "Content-Type": "application/json"}


def configure(monkeypatch):
    monkeypatch.setattr(settings, "nautobot_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "nautobot_token", "test-token")
    monkeypatch.setattr(nautobot, "fetch_nautobot_devices", lambda: [NB_DEVICE])


def test_webhook_unconfigured_returns_503(client):
    assert client.post("/v1/webhooks/nautobot", json=EVENT).status_code == 503


def test_webhook_missing_signature_returns_401(client, monkeypatch):
    configure(monkeypatch)
    assert client.post("/v1/webhooks/nautobot", json=EVENT).status_code == 401


def test_webhook_bad_signature_returns_401(client, monkeypatch):
    configure(monkeypatch)
    body = json.dumps(EVENT).encode()
    headers = {"X-Hook-Signature": "0" * 128, "Content-Type": "application/json"}
    assert client.post("/v1/webhooks/nautobot", content=body, headers=headers).status_code == 401


def test_webhook_valid_signature_triggers_sync(client, monkeypatch):
    configure(monkeypatch)
    body = json.dumps(EVENT).encode()
    resp = client.post("/v1/webhooks/nautobot", content=body, headers=signed(body))
    assert resp.status_code == 200
    assert resp.json()["created"] == 1

    devices = client.get("/v1/devices").json()["items"]
    assert devices[0]["hostname"] == "leaf3"
    assert devices[0]["nautobot_id"] == NB_DEVICE["id"]


def test_webhook_duplicate_delivery_is_harmless(client, monkeypatch):
    configure(monkeypatch)
    body = json.dumps(EVENT).encode()
    first = client.post("/v1/webhooks/nautobot", content=body, headers=signed(body))
    second = client.post("/v1/webhooks/nautobot", content=body, headers=signed(body))
    assert first.json()["created"] == 1
    assert second.json()["created"] == 0
    assert client.get("/v1/devices").json()["total"] == 1

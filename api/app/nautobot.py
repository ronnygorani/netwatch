"""Sync the device cache from Nautobot, the source of truth.

Nautobot owns inventory; our devices table is a read-through cache of it.
Rows are matched by nautobot_id, adopted by ip_address on first sync, and
deactivated when they disappear from the SoT. Local rows without a
nautobot_id (manual/demo devices) are never touched.
"""

import logging
from typing import get_args

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.device import Device
from app.schemas.device import DeviceType

logger = logging.getLogger(__name__)

SUPPORTED_DRIVERS = set(get_args(DeviceType))


def fetch_nautobot_devices() -> list[dict]:
    with httpx.Client(
        base_url=f"{settings.nautobot_url}/api",
        headers={"Authorization": f"Token {settings.nautobot_token}"},
        timeout=10,
    ) as client:
        devices: list[dict] = []
        url = "/dcim/devices/?depth=1&limit=100"
        while url:
            resp = client.get(url)
            resp.raise_for_status()
            page = resp.json()
            devices.extend(page["results"])
            url = page["next"]
        return devices


def map_nautobot_device(nb_device: dict) -> dict | None:
    """Reduce a Nautobot device to cache fields; None if it isn't pollable."""
    primary_ip = nb_device.get("primary_ip4") or {}
    platform = nb_device.get("platform") or {}
    driver = platform.get("network_driver")
    address = (primary_ip.get("address") or "").split("/")[0]
    if not address or driver not in SUPPORTED_DRIVERS:
        return None

    location = nb_device.get("location") or {}
    status = nb_device.get("status") or {}
    return {
        "nautobot_id": nb_device["id"],
        "hostname": nb_device["name"],
        "ip_address": address,
        "site": location.get("name") or "unknown",
        "device_type": driver,
        "is_active": status.get("name") == "Active",
    }


def sync_devices(db: Session, mapped: list[dict]) -> dict:
    """Upsert the cache to mirror the SoT. Returns change counts."""
    created = updated = deactivated = 0
    seen_ids = set()

    for fields in mapped:
        seen_ids.add(fields["nautobot_id"])
        row = db.query(Device).filter(Device.nautobot_id == fields["nautobot_id"]).first()
        if row is None:
            # Adoption: a pre-SoT row with the same address becomes the cache row.
            row = db.query(Device).filter(Device.ip_address == fields["ip_address"]).first()
        if row is None:
            db.add(Device(**fields))
            created += 1
            continue
        changed = False
        for key, value in fields.items():
            if getattr(row, key) != value:
                setattr(row, key, value)
                changed = True
        updated += changed

    # Gone from the SoT means gone from polling; history is preserved.
    for row in db.query(Device).filter(Device.nautobot_id.isnot(None)):
        if row.nautobot_id not in seen_ids and row.is_active:
            row.is_active = False
            deactivated += 1

    db.commit()
    return {"created": created, "updated": updated, "deactivated": deactivated}

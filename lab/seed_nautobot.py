"""Seed Nautobot with the lab topology: location, platform, and the three switches.

Idempotent: safe to rerun, existing objects are reused.

Usage:
    python lab/seed_nautobot.py            # reads NAUTOBOT_TOKEN from .env
"""

import os
import sys

import httpx

NAUTOBOT_URL = os.getenv("NAUTOBOT_URL", "http://localhost:8080")

SWITCHES = {
    "spine1": "172.20.20.11/24",
    "leaf1": "172.20.20.12/24",
    "leaf2": "172.20.20.13/24",
}


def load_token() -> str:
    if token := os.getenv("NAUTOBOT_TOKEN"):
        return token
    with open(os.path.join(os.path.dirname(__file__), "..", ".env")) as f:
        for line in f:
            if line.startswith("NAUTOBOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit("NAUTOBOT_TOKEN not found in environment or .env")


class Nautobot:
    def __init__(self, url: str, token: str):
        self.client = httpx.Client(
            base_url=f"{url}/api",
            headers={"Authorization": f"Token {token}", "Accept": "application/json"},
            timeout=30,
        )

    def get_or_create(self, path: str, lookup: dict, payload: dict) -> dict:
        resp = self.client.get(f"/{path}/", params=lookup)
        resp.raise_for_status()
        results = resp.json()["results"]
        if results:
            print(f"  exists: {path} {lookup}")
            return results[0]
        resp = self.client.post(f"/{path}/", json=payload)
        if resp.status_code >= 400:
            sys.exit(f"FAILED creating {path}: {resp.status_code} {resp.text[:400]}")
        print(f"  created: {path} {lookup}")
        return resp.json()

    def patch(self, path: str, obj_id: str, payload: dict) -> None:
        resp = self.client.patch(f"/{path}/{obj_id}/", json=payload)
        if resp.status_code >= 400:
            sys.exit(f"FAILED patching {path}/{obj_id}: {resp.status_code} {resp.text[:400]}")


def main() -> None:
    nb = Nautobot(NAUTOBOT_URL, load_token())
    active = {"name": "Active"}

    print("Structural objects:")
    loc_type = nb.get_or_create(
        "dcim/location-types",
        {"name": "Site"},
        {"name": "Site", "content_types": ["dcim.device"]},
    )
    location = nb.get_or_create(
        "dcim/locations",
        {"name": "LAB"},
        {"name": "LAB", "location_type": loc_type["id"], "status": active},
    )
    manufacturer = nb.get_or_create("dcim/manufacturers", {"name": "Arista"}, {"name": "Arista"})
    device_type = nb.get_or_create(
        "dcim/device-types",
        {"model": "cEOS-lab"},
        {"manufacturer": manufacturer["id"], "model": "cEOS-lab"},
    )
    # network_driver is what NetWatch's poller consumes as device_type.
    platform = nb.get_or_create(
        "dcim/platforms",
        {"name": "Arista EOS"},
        {"name": "Arista EOS", "network_driver": "arista_eos"},
    )
    role = nb.get_or_create(
        "extras/roles",
        {"name": "lab-switch"},
        {"name": "lab-switch", "content_types": ["dcim.device"], "color": "2196f3"},
    )
    nb.get_or_create(
        "ipam/prefixes",
        {"prefix": "172.20.20.0/24"},
        {"prefix": "172.20.20.0/24", "status": active},
    )

    print("Switches:")
    for hostname, address in SWITCHES.items():
        device = nb.get_or_create(
            "dcim/devices",
            {"name": hostname},
            {
                "name": hostname,
                "role": role["id"],
                "device_type": device_type["id"],
                "platform": platform["id"],
                "location": location["id"],
                "status": active,
            },
        )
        interface = nb.get_or_create(
            "dcim/interfaces",
            {"device_id": device["id"], "name": "Management0"},
            {"device": device["id"], "name": "Management0", "type": "virtual", "status": active},
        )
        ip = nb.get_or_create(
            "ipam/ip-addresses",
            {"address": address},
            {"address": address, "status": active, "namespace": {"name": "Global"}},
        )
        nb.get_or_create(
            "ipam/ip-address-to-interface",
            {"interface": interface["id"], "ip_address": ip["id"]},
            {"interface": interface["id"], "ip_address": ip["id"]},
        )
        nb.patch("dcim/devices", device["id"], {"primary_ip4": ip["id"]})
        print(f"  {hostname} ready: {address}")

    print("Seed complete.")


if __name__ == "__main__":
    main()

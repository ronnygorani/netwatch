import logging
import os
import re
import time

import httpx
from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("poller")

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
SSH_USER = os.getenv("NETMIKO_USERNAME", "")
SSH_PASS = os.getenv("NETMIKO_PASSWORD", "")


def fetch_devices() -> list[dict]:
    with httpx.Client(base_url=API_BASE, timeout=10) as client:
        resp = client.get("/devices")
        resp.raise_for_status()
        return [d for d in resp.json() if d["is_active"]]


def post_metric(payload: dict) -> None:
    with httpx.Client(base_url=API_BASE, timeout=10) as client:
        resp = client.post("/metrics", json=payload)
        resp.raise_for_status()


def parse_cpu(output: str) -> float | None:
    match = re.search(r"(\d+)%\s+(?:five|one)\s+minute", output)
    if match:
        return float(match.group(1))
    match = re.search(r"CPU utilization.*?(\d+)%", output)
    return float(match.group(1)) if match else None


def parse_memory(output: str) -> float | None:
    match = re.search(r"(\d+)K\s+total.*?(\d+)K\s+used", output)
    if match:
        total, used = int(match.group(1)), int(match.group(2))
        return round(used / total * 100, 1) if total else None
    return None


def parse_uptime_seconds(output: str) -> int | None:
    days = int(m.group(1)) if (m := re.search(r"(\d+)\s+day", output)) else 0
    hours = int(m.group(1)) if (m := re.search(r"(\d+)\s+hour", output)) else 0
    minutes = int(m.group(1)) if (m := re.search(r"(\d+)\s+minute", output)) else 0
    if days == 0 and hours == 0 and minutes == 0:
        return None
    return days * 86400 + hours * 3600 + minutes * 60


def poll_device(device: dict) -> dict:
    connection_params = {
        "device_type": device["device_type"],
        "host": device["ip_address"],
        "port": device["port"],
        "username": SSH_USER,
        "password": SSH_PASS,
        "timeout": 15,
        "fast_cli": False,
    }
    try:
        with ConnectHandler(**connection_params) as conn:
            cpu_out = conn.send_command("show processes cpu | include CPU utilization")
            mem_out = conn.send_command("show processes memory | include Processor")
            ver_out = conn.send_command("show version | include uptime")

        return {
            "device_id": device["id"],
            "status": "up",
            "cpu_percent": parse_cpu(cpu_out),
            "memory_percent": parse_memory(mem_out),
            "uptime_seconds": parse_uptime_seconds(ver_out),
            "raw_output": f"CPU:\n{cpu_out}\n\nMEM:\n{mem_out}\n\nVER:\n{ver_out}",
        }
    except NetmikoAuthenticationException:
        logger.warning("Auth failed for %s (%s)", device["hostname"], device["ip_address"])
        return {"device_id": device["id"], "status": "unreachable"}
    except NetmikoTimeoutException:
        logger.warning("Timeout for %s (%s)", device["hostname"], device["ip_address"])
        return {"device_id": device["id"], "status": "unreachable"}
    except Exception as exc:
        logger.error("Unexpected error polling %s: %s", device["hostname"], exc)
        return {"device_id": device["id"], "status": "down"}


def run_poll_cycle() -> None:
    logger.info("Starting poll cycle")
    try:
        devices = fetch_devices()
    except Exception as exc:
        logger.error("Could not fetch device list: %s", exc)
        return

    logger.info("Polling %d active device(s)", len(devices))
    for device in devices:
        logger.info("Polling %s (%s)", device["hostname"], device["ip_address"])
        metric = poll_device(device)
        try:
            post_metric(metric)
            logger.info(
                "  %s → status=%s cpu=%s%% mem=%s%%",
                device["hostname"],
                metric["status"],
                metric.get("cpu_percent", "n/a"),
                metric.get("memory_percent", "n/a"),
            )
        except Exception as exc:
            logger.error("Failed to post metric for %s: %s", device["hostname"], exc)

    logger.info("Poll cycle complete")


def main() -> None:
    logger.info("NetAuto poller starting | interval=%ds | api=%s", POLL_INTERVAL, API_BASE)
    while True:
        run_poll_cycle()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

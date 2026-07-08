import logging
import os
import time

import httpx
from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
from parsers import parse_cpu, parse_memory, parse_uptime_seconds

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("poller")

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
SSH_USER = os.getenv("NETMIKO_USERNAME", "")
SSH_PASS = os.getenv("NETMIKO_PASSWORD", "")

# Keep comfortably under the API's 10_000-char schema cap on raw_output.
RAW_OUTPUT_LIMIT = 8_000


def fetch_devices(client: httpx.Client) -> list[dict]:
    resp = client.get("/devices")
    resp.raise_for_status()
    return [d for d in resp.json() if d["is_active"]]


def post_metric(client: httpx.Client, payload: dict) -> None:
    resp = client.post("/metrics", json=payload)
    resp.raise_for_status()


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

        raw = f"CPU:\n{cpu_out}\n\nMEM:\n{mem_out}\n\nVER:\n{ver_out}"
        return {
            "device_id": device["id"],
            "status": "up",
            "cpu_percent": parse_cpu(cpu_out),
            "memory_percent": parse_memory(mem_out),
            "uptime_seconds": parse_uptime_seconds(ver_out),
            "raw_output": raw[:RAW_OUTPUT_LIMIT],
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

    # One client for the whole cycle: connection reuse instead of a fresh
    # TCP handshake per request (one GET + one POST per device).
    with httpx.Client(base_url=API_BASE, timeout=10) as client:
        try:
            devices = fetch_devices(client)
        except Exception as exc:
            logger.error("Could not fetch device list: %s", exc)
            return

        logger.info("Polling %d active device(s)", len(devices))
        for device in devices:
            logger.info("Polling %s (%s)", device["hostname"], device["ip_address"])
            metric = poll_device(device)
            try:
                post_metric(client, metric)
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
    logger.info("NetWatch poller starting | interval=%ds | api=%s", POLL_INTERVAL, API_BASE)
    while True:
        run_poll_cycle()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

"""Job executors, run by the worker process.

Each executor receives a job id, does the work, and records the outcome.
The dispatcher owns the state transitions so every job type gets identical
running/succeeded/failed bookkeeping.
"""

import hashlib
import logging
from datetime import UTC, datetime

from napalm import get_network_driver

from app.config import settings
from app.database import SessionLocal
from app.models.audit import AuditEvent
from app.models.config_backup import ConfigBackup
from app.models.device import Device
from app.models.job import Job

logger = logging.getLogger(__name__)

# device_type -> NAPALM driver. Mirrors the poller's map.
NAPALM_DRIVERS = {
    "arista_eos": "eos",
    "cisco_ios": "ios",
    "cisco_xe": "ios",
    "cisco_nxos": "nxos",
    "juniper_junos": "junos",
}


def _connect(device: Device):
    driver_name = NAPALM_DRIVERS[device.device_type]
    driver = get_network_driver(driver_name)
    optional_args = {"port": device.port} if driver_name != "eos" else {}
    conn = driver(
        hostname=device.ip_address,
        username=settings.netmiko_username,
        password=settings.netmiko_password,
        timeout=30,
        optional_args=optional_args,
    )
    conn.open()
    return conn


def _get_running_config(device: Device) -> str:
    conn = _connect(device)
    try:
        return conn.get_config(retrieve="running")["running"]
    finally:
        conn.close()


def _backup_one(db, device: Device) -> str:
    """Fetch a device's config; store only if it changed. Returns an outcome word."""
    content = _get_running_config(device)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    latest = (
        db.query(ConfigBackup)
        .filter(ConfigBackup.device_id == device.id)
        .order_by(ConfigBackup.taken_at.desc())
        .first()
    )
    if latest and latest.content_hash == content_hash:
        return "unchanged"

    db.add(ConfigBackup(device_id=device.id, content_hash=content_hash, content=content))
    return "backed_up"


def execute_config_backup(db, job: Job) -> dict:
    device_ids = job.params.get("device_ids")
    query = db.query(Device).filter(Device.is_active.is_(True))
    if device_ids:
        query = query.filter(Device.id.in_(device_ids))
    devices = query.filter(Device.device_type.in_(NAPALM_DRIVERS)).all()

    outcomes = {"backed_up": 0, "unchanged": 0, "failed": 0}
    errors: dict[str, str] = {}
    for device in devices:
        try:
            outcomes[_backup_one(db, device)] += 1
        except Exception as exc:  # one device failing must not fail the batch
            outcomes["failed"] += 1
            errors[device.hostname] = str(exc)
            logger.warning("Backup failed for %s: %s", device.hostname, exc)

    db.commit()
    result = {"devices": len(devices), **outcomes}
    if errors:
        result["errors"] = errors
    return result


def _apply_to_device(device: Device, snippet: str) -> dict:
    """Push config to one device with validation and automatic rollback.

    The device computes the diff itself (compare_config), so what the approver
    reviewed is what the device says it will do, not our guess.
    """
    conn = _connect(device)
    try:
        conn.load_merge_candidate(config=snippet)
        diff = conn.compare_config()
        if not diff.strip():
            conn.discard_config()
            return {"status": "no_change", "diff": ""}
        conn.commit_config()
    except Exception:
        try:
            conn.discard_config()
        except Exception:
            logger.warning("Could not discard candidate config on %s", device.hostname)
        raise
    finally:
        conn.close()

    # Post-change validation on a fresh session: if the device stopped answering
    # after its own commit, the change broke it and must come back out.
    try:
        verify = _connect(device)
        try:
            verify.get_facts()
        finally:
            verify.close()
    except Exception as exc:
        rolled_back = False
        try:
            recover = _connect(device)
            try:
                recover.rollback()
                rolled_back = True
            finally:
                recover.close()
        except Exception:
            logger.exception("Rollback failed for %s", device.hostname)
        return {
            "status": "rolled_back" if rolled_back else "failed_validation",
            "diff": diff,
            "error": str(exc),
        }

    return {"status": "applied", "diff": diff}


def execute_change_job(db, job: Job) -> dict:
    from app.models.change import Change

    change = db.get(Change, job.params["change_id"])
    if change is None:
        raise ValueError(f"Change {job.params['change_id']} not found")

    devices = db.query(Device).filter(Device.id.in_(change.device_ids)).all()
    diffs: dict[str, str] = {}
    outcomes: dict[str, str] = {}

    for device in devices:
        # Pre-change snapshot so the previous state is always recoverable.
        try:
            _backup_one(db, device)
        except Exception as exc:
            logger.warning("Pre-change backup failed for %s: %s", device.hostname, exc)

        try:
            result = _apply_to_device(device, change.config_snippet)
            outcomes[device.hostname] = result["status"]
            diffs[device.hostname] = result.get("diff", "")
        except Exception as exc:
            outcomes[device.hostname] = "failed"
            diffs[device.hostname] = ""
            logger.exception("Change %s failed on %s", change.id, device.hostname)
            change.result = {"error_device": device.hostname, "error": str(exc)}

        # Post-change snapshot records what the device looks like now.
        try:
            _backup_one(db, device)
        except Exception as exc:
            logger.warning("Post-change backup failed for %s: %s", device.hostname, exc)

    change.diff = diffs
    change.executed_at = datetime.now(UTC)
    statuses = set(outcomes.values())
    if statuses <= {"applied", "no_change"}:
        change.status = "succeeded"
    elif "rolled_back" in statuses:
        change.status = "rolled_back"
    else:
        change.status = "failed"
    change.result = {**(change.result or {}), "devices": outcomes}

    db.add(
        AuditEvent(
            actor=job.requested_by,
            actor_type="service",
            action=f"change.{change.status}",
            resource=f"changes/{change.id}",
            detail={"devices": outcomes},
        )
    )
    db.commit()
    return {"change_id": change.id, "status": change.status, "devices": outcomes}


EXECUTORS = {
    "config_backup": execute_config_backup,
    "execute_change": execute_change_job,
}


def run_job(job_id: int) -> None:
    """Dispatcher: owns state transitions; delegates the work to an executor."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()

        try:
            job.result = EXECUTORS[job.type](db, job)
            job.status = "succeeded"
        except Exception as exc:
            db.rollback()
            job.status = "failed"
            job.error = str(exc)
            logger.exception("Job %s (%s) failed", job_id, job.type)
        job.finished_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()

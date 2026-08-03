import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.config_backup import ConfigBackup
from app.models.job import Job
from app.models.metric import Metric
from app.models.poller_heartbeat import PollerHeartbeat
from app.queue import enqueue_job
from app.schemas.heartbeat import HeartbeatCreate, HeartbeatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/poller", tags=["poller"])


@router.post("/heartbeat", response_model=HeartbeatResponse, status_code=status.HTTP_201_CREATED)
def record_heartbeat(
    payload: HeartbeatCreate,
    db: Session = Depends(get_db),
    _key: ApiKey = Depends(require_scope("metrics:write")),
):
    heartbeat = db.get(PollerHeartbeat, payload.name)
    if heartbeat is None:
        heartbeat = PollerHeartbeat(name=payload.name)
        db.add(heartbeat)
    heartbeat.last_seen_at = datetime.now(UTC)
    heartbeat.devices_polled = payload.devices_polled
    heartbeat.failures = payload.failures
    heartbeat.cycle_seconds = payload.cycle_seconds
    heartbeat.interval_seconds = payload.interval_seconds

    # Retention rides the heartbeat cadence: one bounded, indexed DELETE per
    # cycle instead of a scheduler we don't have yet (FM-D4; revisit at P6 jobs).
    if settings.metric_retention_days > 0:
        cutoff = datetime.now(UTC) - timedelta(days=settings.metric_retention_days)
        db.query(Metric).filter(Metric.collected_at < cutoff).delete()

    queued_backup = _maybe_schedule_backup(db)

    db.commit()
    if queued_backup is not None:
        # Best effort: the heartbeat is a liveness signal and must not fail
        # because the queue is unavailable. The job row persists either way and
        # a later heartbeat will find it pending rather than queueing a second.
        try:
            enqueue_job(queued_backup)
        except Exception:
            logger.warning("Could not enqueue scheduled backup job %s", queued_backup)
    db.refresh(heartbeat)
    return heartbeat


def _maybe_schedule_backup(db: Session) -> int | None:
    """Queue a config backup when the newest one is older than the interval.

    Same piggyback pattern as retention: the heartbeat is a reliable tick, so
    periodic work rides it rather than requiring a scheduler.
    """
    if settings.backup_interval_hours <= 0:
        return None
    cutoff = datetime.now(UTC) - timedelta(hours=settings.backup_interval_hours)
    newest = db.query(func.max(ConfigBackup.taken_at)).scalar()
    if newest is not None and newest.replace(tzinfo=UTC) > cutoff:
        return None
    # Avoid piling up duplicates if the worker is down or slow.
    pending = (
        db.query(Job)
        .filter(Job.type == "config_backup", Job.status.in_(("queued", "running")))
        .first()
    )
    if pending is not None:
        return None
    job = Job(type="config_backup", params={}, requested_by="scheduler")
    db.add(job)
    db.flush()
    return job.id


@router.get("/status", response_model=list[HeartbeatResponse])
def poller_status(db: Session = Depends(get_db)):
    return db.query(PollerHeartbeat).order_by(PollerHeartbeat.name).all()

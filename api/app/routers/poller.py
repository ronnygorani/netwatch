from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.metric import Metric
from app.models.poller_heartbeat import PollerHeartbeat
from app.schemas.heartbeat import HeartbeatCreate, HeartbeatResponse

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

    db.commit()
    db.refresh(heartbeat)
    return heartbeat


@router.get("/status", response_model=list[HeartbeatResponse])
def poller_status(db: Session = Depends(get_db)):
    return db.query(PollerHeartbeat).order_by(PollerHeartbeat.name).all()

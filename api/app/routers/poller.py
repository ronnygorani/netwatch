from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.database import get_db
from app.models.api_key import ApiKey
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
    db.commit()
    db.refresh(heartbeat)
    return heartbeat


@router.get("/status", response_model=list[HeartbeatResponse])
def poller_status(db: Session = Depends(get_db)):
    return db.query(PollerHeartbeat).order_by(PollerHeartbeat.name).all()

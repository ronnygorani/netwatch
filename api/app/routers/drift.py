from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app import audit
from app.database import get_db
from app.models.drift import DriftEvent
from app.models.user import User
from app.schemas.drift import DriftAcknowledge, DriftSummary
from app.schemas.pagination import Page
from app.security import require_role

router = APIRouter(prefix="/drift", tags=["drift"])


def _get_event(db: Session, event_id: int) -> DriftEvent:
    event = db.get(DriftEvent, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drift event not found")
    return event


@router.get("", response_model=Page[DriftSummary])
def list_drift(
    device_id: int | None = None,
    classification: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(DriftEvent).order_by(DriftEvent.id.desc())
    if device_id is not None:
        query = query.filter(DriftEvent.device_id == device_id)
    if classification:
        query = query.filter(DriftEvent.classification == classification)
    if status_filter:
        query = query.filter(DriftEvent.status == status_filter)
    total = query.count()
    return Page(
        items=query.offset(offset).limit(limit).all(), total=total, limit=limit, offset=offset
    )


@router.get("/{event_id}", response_model=DriftSummary)
def get_drift(event_id: int, db: Session = Depends(get_db)):
    return _get_event(db, event_id)


@router.get("/{event_id}/diff", response_class=PlainTextResponse)
def get_drift_diff(
    event_id: int,
    db: Session = Depends(get_db),
    # A config diff can carry secrets; same reasoning as backups:read on content.
    _user: User = Depends(require_role("viewer")),
):
    return _get_event(db, event_id).diff


@router.post("/{event_id}/acknowledge", response_model=DriftSummary)
def acknowledge_drift(
    event_id: int,
    payload: DriftAcknowledge,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator")),
):
    event = _get_event(db, event_id)
    if event.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Drift event is already '{event.status}'",
        )
    event.status = "acknowledged"
    event.acknowledged_by = user.username
    event.acknowledged_at = datetime.now(UTC)
    event.note = payload.note
    audit.record(
        db,
        actor=user.username,
        actor_type="human",
        action="drift.acknowledge",
        resource=f"drift/{event.id}",
        detail={"device_id": event.device_id, "note": payload.note},
        request=request,
    )
    db.commit()
    db.refresh(event)
    return event

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app import audit
from app.database import get_db
from app.models.change import Change
from app.models.device import Device
from app.models.job import Job
from app.models.user import User
from app.queue import enqueue_job
from app.schemas.change import ChangeCreate, ChangeReject, ChangeResponse
from app.schemas.pagination import Page
from app.security import require_role

router = APIRouter(prefix="/changes", tags=["changes"])


def _get_change(db: Session, change_id: int) -> Change:
    change = db.get(Change, change_id)
    if change is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change not found")
    return change


def _require_status(change: Change, expected: str) -> None:
    if change.status != expected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Change is '{change.status}'; this action requires '{expected}'",
        )


@router.post("", response_model=ChangeResponse, status_code=status.HTTP_201_CREATED)
def propose_change(
    payload: ChangeCreate,
    request: Request,
    db: Session = Depends(get_db),
    author: User = Depends(require_role("operator")),
):
    known = {d.id for d in db.query(Device.id).filter(Device.id.in_(payload.device_ids)).all()}
    missing = set(payload.device_ids) - known
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown device ids: {sorted(missing)}",
        )

    change = Change(
        title=payload.title,
        description=payload.description,
        config_snippet=payload.config_snippet,
        device_ids=payload.device_ids,
        author_id=author.id,
        status="proposed",
    )
    db.add(change)
    db.flush()
    audit.record(
        db,
        actor=author.username,
        actor_type="human",
        action="change.propose",
        resource=f"changes/{change.id}",
        detail={"title": change.title, "device_ids": change.device_ids},
        request=request,
    )
    db.commit()
    db.refresh(change)
    return change


@router.get("", response_model=Page[ChangeResponse])
def list_changes(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Change).order_by(Change.id.desc())
    if status_filter:
        query = query.filter(Change.status == status_filter)
    total = query.count()
    return Page(
        items=query.offset(offset).limit(limit).all(), total=total, limit=limit, offset=offset
    )


@router.get("/{change_id}", response_model=ChangeResponse)
def get_change(change_id: int, db: Session = Depends(get_db)):
    return _get_change(db, change_id)


@router.post("/{change_id}/approve", response_model=ChangeResponse)
def approve_change(
    change_id: int,
    request: Request,
    db: Session = Depends(get_db),
    approver: User = Depends(require_role("approver")),
):
    change = _get_change(db, change_id)
    _require_status(change, "proposed")
    # The two-person rule, enforced structurally rather than by policy: the
    # author of a change can never be its approver, whatever their role.
    if change.author_id == approver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot approve your own change",
        )

    change.status = "approved"
    change.approver_id = approver.id
    change.approved_at = datetime.now(UTC)
    audit.record(
        db,
        actor=approver.username,
        actor_type="human",
        action="change.approve",
        resource=f"changes/{change.id}",
        request=request,
    )
    db.commit()
    db.refresh(change)
    return change


@router.post("/{change_id}/reject", response_model=ChangeResponse)
def reject_change(
    change_id: int,
    payload: ChangeReject,
    request: Request,
    db: Session = Depends(get_db),
    approver: User = Depends(require_role("approver")),
):
    change = _get_change(db, change_id)
    _require_status(change, "proposed")
    change.status = "rejected"
    change.approver_id = approver.id
    change.rejection_reason = payload.reason
    audit.record(
        db,
        actor=approver.username,
        actor_type="human",
        action="change.reject",
        resource=f"changes/{change.id}",
        detail={"reason": payload.reason},
        request=request,
    )
    db.commit()
    db.refresh(change)
    return change


@router.post("/{change_id}/execute", status_code=status.HTTP_202_ACCEPTED)
def execute_change(
    change_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator")),
):
    change = _get_change(db, change_id)
    _require_status(change, "approved")

    job = Job(
        type="execute_change",
        params={"change_id": change.id},
        requested_by=user.username,
    )
    db.add(job)
    change.status = "executing"
    db.flush()
    audit.record(
        db,
        actor=user.username,
        actor_type="human",
        action="change.execute",
        resource=f"changes/{change.id}",
        detail={"job_id": job.id},
        request=request,
    )
    db.commit()
    enqueue_job(job.id)
    return {"change_id": change.id, "job_id": job.id, "status": "executing"}

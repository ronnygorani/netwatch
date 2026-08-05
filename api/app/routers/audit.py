from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.change import AuditEventResponse
from app.schemas.pagination import Page
from app.security import require_role

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=Page[AuditEventResponse])
def list_audit_events(
    actor: str | None = None,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    # Reading the trail is itself privileged: it reveals who did what, when.
    _user: User = Depends(require_role("approver")),
):
    query = db.query(AuditEvent).order_by(AuditEvent.id.desc())
    if actor:
        query = query.filter(AuditEvent.actor == actor)
    if action:
        query = query.filter(AuditEvent.action == action)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)

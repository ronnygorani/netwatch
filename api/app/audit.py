"""Recording side of the audit trail.

Append-only by construction: this module only ever inserts. The caller's
transaction commits the event alongside the change it describes, so an action
and its audit record land together or not at all.
"""

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def record(
    db: Session,
    *,
    actor: str,
    actor_type: str,
    action: str,
    resource: str,
    detail: dict | None = None,
    request: Request | None = None,
    on_behalf_of: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor=actor,
            actor_type=actor_type,
            on_behalf_of=on_behalf_of,
            action=action,
            resource=resource,
            detail=detail,
            source_ip=request.client.host if request and request.client else None,
        )
    )

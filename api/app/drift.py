"""Detect config changes and classify them against the change workflow."""

import difflib
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.change import Change
from app.models.config_backup import ConfigBackup
from app.models.device import Device
from app.models.drift import DriftEvent

# "executing" is required: the post-change snapshot is taken inside the job,
# before the change reaches a terminal status.
EXECUTION_STATUSES = ("executing", "succeeded", "failed", "rolled_back")

_CANDIDATE_LIMIT = 200


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def build_diff(previous: str, current: str) -> str:
    return "".join(
        difflib.unified_diff(
            previous.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile="previous",
            tofile="current",
        )
    )


def find_explaining_change(db: Session, device: Device, detected_at: datetime) -> Change | None:
    window_start = detected_at - timedelta(minutes=settings.drift_correlation_minutes)
    # device_ids is JSON; array containment is not portable across SQLite and
    # Postgres, so the recent slice is filtered here.
    recent = (
        db.query(Change)
        .filter(Change.status.in_(EXECUTION_STATUSES))
        .order_by(Change.id.desc())
        .limit(_CANDIDATE_LIMIT)
        .all()
    )
    for change in recent:
        if device.id not in (change.device_ids or []):
            continue
        stamp = change.executed_at or change.approved_at
        if stamp is not None and _aware(stamp) >= window_start:
            return change
    return None


def record(
    db: Session, device: Device, previous: ConfigBackup, current: ConfigBackup
) -> DriftEvent:
    """Create a drift event for a config change. Caller commits."""
    detected_at = datetime.now(UTC)
    change = find_explaining_change(db, device, detected_at)
    event = DriftEvent(
        device_id=device.id,
        detected_at=detected_at,
        previous_backup_id=previous.id,
        current_backup_id=current.id,
        previous_hash=previous.content_hash,
        current_hash=current.content_hash,
        diff=build_diff(previous.content, current.content),
        classification="authorized" if change else "unauthorized",
        change_id=change.id if change else None,
    )
    if change is not None:
        # Already reviewed in the workflow, so "open" means nobody has explained it.
        event.status = "acknowledged"
        event.acknowledged_by = "change-workflow"
        event.acknowledged_at = detected_at
        event.note = f"Explained by change {change.id}: {change.title}"
    else:
        event.status = "open"
    db.add(event)
    return event

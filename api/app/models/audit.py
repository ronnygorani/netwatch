from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditEvent(Base):
    """Append-only record of every state-changing action.

    No endpoint updates or deletes these rows: an audit trail that can be
    rewritten is not an audit trail. actor_type anticipates the AI assistant
    acting on a person's behalf (docs/AI-ASSISTANT.md).
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # human | service | assistant
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    on_behalf_of: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(128), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

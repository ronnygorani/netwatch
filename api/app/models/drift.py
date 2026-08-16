from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DriftEvent(Base):
    """An observed change to a device's running config, authorized or not."""

    __tablename__ = "drift_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    # Backups are prunable; the hashes keep the event self-describing.
    previous_backup_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("config_backups.id", ondelete="SET NULL"), nullable=True
    )
    current_backup_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("config_backups.id", ondelete="SET NULL"), nullable=True
    )
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    diff: Mapped[str] = mapped_column(Text, nullable=False)

    classification: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    change_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("changes.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", index=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

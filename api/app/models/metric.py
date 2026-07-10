from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.database import Base


class Metric(Base):
    __tablename__ = "metrics"

    # Serves the latest-per-device and per-device-history queries.
    __table_args__ = (Index("ix_metrics_device_id_collected_at", "device_id", "collected_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # passive_deletes defers row deletion to the DB's ON DELETE CASCADE (FM-A9).
    device = relationship("Device", backref=backref("metrics", passive_deletes=True))

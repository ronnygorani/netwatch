from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PollerHeartbeat(Base):
    """One row per collector, upserted each cycle. Staleness of last_seen_at
    is the dead-poller signal (FM-P4)."""

    __tablename__ = "poller_heartbeats"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Server clock, set at ingest.
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    devices_polled: Mapped[int] = mapped_column(Integer, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HeartbeatCreate(BaseModel):
    name: str = Field(default="poller", min_length=1, max_length=64)
    devices_polled: int = Field(..., ge=0)
    failures: int = Field(..., ge=0)
    cycle_seconds: float = Field(..., ge=0)
    interval_seconds: int = Field(..., gt=0)


class HeartbeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    last_seen_at: datetime
    devices_polled: int
    failures: int
    cycle_seconds: float
    interval_seconds: int

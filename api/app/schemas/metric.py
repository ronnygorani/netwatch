from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MetricCreate(BaseModel):
    device_id: int
    status: str = Field(..., pattern="^(up|down|unreachable)$")
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    uptime_seconds: int | None = Field(default=None, ge=0)
    raw_output: str | None = None


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    collected_at: datetime
    status: str
    cpu_percent: float | None
    memory_percent: float | None
    uptime_seconds: int | None

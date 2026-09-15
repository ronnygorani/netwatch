from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DriftSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    detected_at: datetime
    previous_backup_id: int | None
    current_backup_id: int | None
    previous_hash: str
    current_hash: str
    classification: str
    change_id: int | None
    status: str
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    note: str | None


class DriftAcknowledge(BaseModel):
    note: str = Field(..., min_length=1, max_length=1000)

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Closed set: unknown job types are a 422 at the boundary.
JobType = Literal["config_backup"]


class JobCreate(BaseModel):
    type: JobType
    # config_backup accepts {"device_ids": [1, 2]}; empty means all active devices.
    params: dict = Field(default_factory=dict)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    params: dict
    result: dict | None
    error: str | None
    requested_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class BackupSummary(BaseModel):
    """Metadata only; content is served by the scoped content endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    taken_at: datetime
    content_hash: str

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChangeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    # Config lines merged into the running config of every target device.
    config_snippet: str = Field(..., min_length=1, max_length=20_000)
    device_ids: list[int] = Field(..., min_length=1)


class ChangeReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class ChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    config_snippet: str
    device_ids: list[int]
    status: str
    author_id: int
    approver_id: int | None
    rejection_reason: str | None
    diff: dict | None
    result: dict | None
    created_at: datetime
    approved_at: datetime | None
    executed_at: datetime | None


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    actor: str
    actor_type: str
    on_behalf_of: str | None
    action: str
    resource: str
    detail: dict | None
    source_ip: str | None

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChangeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    # Either supply config lines directly, or name a template to render per
    # device from its resolved variables. Exactly one of the two.
    config_snippet: str | None = Field(default=None, min_length=1, max_length=20_000)
    template_name: str | None = Field(default=None, max_length=64)
    device_ids: list[int] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _one_source(self) -> "ChangeCreate":
        if bool(self.config_snippet) == bool(self.template_name):
            raise ValueError("provide exactly one of config_snippet or template_name")
        return self


class ChangeReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class ChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    config_snippet: str
    template_name: str | None
    rendered: dict | None
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

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scope = Literal["global", "site", "device"]


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    body: str = Field(..., min_length=1, max_length=50_000)


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    body: str
    created_at: datetime


class VariableSet(BaseModel):
    scope: Scope
    # Null for global, site name for site, device id (as a string) for device.
    scope_ref: str | None = Field(default=None, max_length=64)
    data: dict

    @model_validator(mode="after")
    def _ref_matches_scope(self) -> "VariableSet":
        if self.scope == "global" and self.scope_ref:
            raise ValueError("global variables take no scope_ref")
        if self.scope != "global" and not self.scope_ref:
            raise ValueError(f"{self.scope} variables require a scope_ref")
        return self


class VariableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: str
    scope_ref: str | None
    data: dict
    updated_at: datetime


class RenderResponse(BaseModel):
    device_id: int
    hostname: str
    rendered: str

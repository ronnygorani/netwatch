from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


class DeviceCreate(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=64)
    ip_address: IPvAnyAddress
    site: str = Field(..., min_length=1, max_length=64)
    device_type: str = Field(default="cisco_ios", max_length=32)
    port: int = Field(default=22, ge=1, le=65535)
    is_active: bool = True


class DeviceUpdate(BaseModel):
    hostname: str | None = Field(default=None, max_length=64)
    site: str | None = Field(default=None, max_length=64)
    device_type: str | None = Field(default=None, max_length=32)
    port: int | None = Field(default=None, ge=1, le=65535)
    is_active: bool | None = None


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hostname: str
    ip_address: str
    site: str
    device_type: str
    port: int
    is_active: bool
    created_at: datetime

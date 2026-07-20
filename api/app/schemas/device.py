from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress

# Netmiko platform driver names the poller can actually speak (FM-E8).
DeviceType = Literal["cisco_ios", "cisco_xe", "cisco_nxos", "arista_eos", "juniper_junos"]


class DeviceCreate(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=64)
    ip_address: IPvAnyAddress
    site: str = Field(..., min_length=1, max_length=64)
    device_type: DeviceType = "cisco_ios"
    port: int = Field(default=22, ge=1, le=65535)
    is_active: bool = True


class DeviceUpdate(BaseModel):
    # min_length mirrors DeviceCreate: omit a field to leave it unchanged, "" is invalid.
    hostname: str | None = Field(default=None, min_length=1, max_length=64)
    site: str | None = Field(default=None, min_length=1, max_length=64)
    device_type: DeviceType | None = None
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
    nautobot_id: str | None
    created_at: datetime

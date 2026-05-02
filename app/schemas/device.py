from pydantic import BaseModel, field_validator, IPvAnyAddress
from typing import Optional
import re

class DeviceCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    device_type: str = "cisco_ios"
    username: str
    password: str
    secret: Optional[str] = None

    @field_validator("host")
    @classmethod
    def host_must_be_valid_ip(cls, v):
        try:
            IPvAnyAddress(v)
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")
        return v

    @field_validator("port")
    @classmethod
    def port_must_be_valid(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("name")
    @classmethod
    def name_must_be_clean(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 50:
            raise ValueError("Name cannot exceed 50 characters")
        return v

    @field_validator("device_type")
    @classmethod
    def device_type_must_be_supported(cls, v):
        allowed = {
            "cisco_ios", "cisco_xe", "cisco_nxos",
            "juniper_junos", "arista_eos", "huawei"
        }
        if v not in allowed:
            raise ValueError(f"Unsupported device type. Allowed: {allowed}")
        return v

    @field_validator("username", "password")
    @classmethod
    def must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v


class DeviceOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    device_type: str
    owner_id: int

    model_config = {"from_attributes": True}


class CommandRequest(BaseModel):
    command: str

    @field_validator("command")
    @classmethod
    def command_must_be_show(cls, v):
        if not v.strip().lower().sta
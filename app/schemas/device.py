from pydantic import BaseModel
from typing import Optional

class DeviceCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    device_type: str = "cisco_ios"
    username: str
    password: str
    secret: Optional[str] = None

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

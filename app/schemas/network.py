from pydantic import BaseModel
from typing import Optional, List

class Interface(BaseModel):
    interface: str
    ip: Optional[str] = None
    ok: Optional[str] = None
    method: Optional[str] = None
    status: str
    protocol: str

class Route(BaseModel):
    protocol: str        # C = connected, S = static, O = OSPF
    network: str
    mask: Optional[str] = None
    next_hop: Optional[str] = None
    interface: Optional[str] = None
    metric: Optional[str] = None

class ArpEntry(BaseModel):
    protocol: str
    ip: str
    age: Optional[str] = None
    mac: str
    type: str
    interface: str

class InterfaceDetail(BaseModel):
    interface: str
    status: str
    protocol: str
    ip: Optional[str] = None
    mask: Optional[str] = None
    mtu: Optional[str] = None
    duplex: Optional[str] = None
    speed: Optional[str] = None

class ConfigSection(BaseModel):
    hostname: Optional[str] = None
    interfaces: List[InterfaceDetail] = []
    raw: str  

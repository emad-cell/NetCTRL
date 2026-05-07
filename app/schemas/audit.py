from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AuditLogOut(BaseModel):
    id:         int
    user_id:    int
    device_id:  Optional[int] = None
    action:     str
    detail:     Optional[str] = None
    status:     str
    error:      Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
from sqlalchemy.orm import Session
from app.db.models import AuditLog
from typing import Optional

def log_action(
    db: Session,
    user_id: int,
    action: str,
    status: str,
    device_id: Optional[int] = None,
    detail: Optional[str] = None,
    error: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Creates an audit log entry for every config-changing action.
    Call this after every SSH config operation.
    """
    entry = AuditLog(
        user_id=user_id,
        device_id=device_id,
        action=action,
        detail=detail,
        status=status,
        error=error,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
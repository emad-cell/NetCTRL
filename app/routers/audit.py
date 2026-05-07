from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.database import get_db
from app.db.models import AuditLog, User
from app.schemas.audit import AuditLogOut
from app.dependencies import get_current_user, AdminOnly

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("/", response_model=list[AuditLogOut])
def get_audit_logs(
    device_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(AdminOnly)   # Admin only
):
    """
    Returns audit logs. Admin only.
    Optional filters: device_id, status (success/failed), limit.
    """
    query = db.query(AuditLog)

    if device_id:
        query = query.filter(AuditLog.device_id == device_id)
    if status:
        query = query.filter(AuditLog.status == status)

    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()

@router.get("/my", response_model=list[AuditLogOut])
def get_my_logs(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Any role
):
    """Returns audit logs for the current user only."""
    return (
        db.query(AuditLog)
        .filter(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User, UserRole
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None or user.is_active is False:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def require_role(*roles: UserRole):
    """
    Factory function — returns a dependency that checks the user's role.
    Usage: Depends(require_role(UserRole.admin, UserRole.operator))
    """
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {[r.value for r in roles]}"
            )
        return current_user
    return checker

# ── Shortcuts ──────────────────────────────────────────────
AdminOnly    = require_role(UserRole.admin)
OperatorPlus = require_role(UserRole.admin, UserRole.operator)
AnyRole      = require_role(UserRole.admin, UserRole.operator, UserRole.viewer)
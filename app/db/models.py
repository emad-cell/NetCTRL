import enum

from sqlalchemy import Column, Enum, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime ,timezone
from app.db.database import Base

class UserRole(str, enum.Enum):
    admin    = "admin"
    operator = "operator"
    viewer   = "viewer"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role= Column(Enum(UserRole), default=UserRole.viewer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # One user can manage many devices
    devices = relationship("Device", back_populates="owner")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)           # e.g. "R1", "Core-Switch"
    host = Column(String, nullable=False)           # IP address
    port = Column(Integer, default=22)
    device_type = Column(String, default="cisco_ios")  # Netmiko device type
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)       # encrypted at rest
    secret = Column(String, nullable=True)          # encrypted at rest when provided
    owner_id = Column(Integer, ForeignKey("users.id"),index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="devices")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id   = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    action      = Column(String, nullable=False)   # e.g. "config/hostname"
    detail      = Column(String, nullable=True)    # e.g. "hostname set to R1"
    status      = Column(String, nullable=False)   # "success" or "failed"
    error       = Column(String, nullable=True)    # error message if failed
    ip_address  = Column(String, nullable=True)    # client IP
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user   = relationship("User", backref="audit_logs")
    device = relationship("Device", backref="audit_logs")
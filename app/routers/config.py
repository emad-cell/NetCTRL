from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, IPvAnyAddress
from typing import Optional, Any
import re
from app.db.database import get_db
from app.db.models import Device, User
from app.services.audit import log_action
from app.services.ssh import ssh_connect
from app.dependencies import get_current_user, AdminOnly, OperatorPlus

router = APIRouter(prefix="/devices", tags=["Config"])

# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_device_or_404(device_id: int, user_id: Any, db: Session) -> Device:
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.owner_id == user_id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

def _send_config(conn, commands: list[str]) -> str:
    output = conn.send_config_set(commands)
    conn.save_config()
    return output

def _get_client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None

# ── Schemas ────────────────────────────────────────────────────────────────────

class HostnameRequest(BaseModel):
    hostname: str

    @field_validator("hostname")
    @classmethod
    def hostname_must_be_valid(cls, v):
        v = v.strip()
        if not re.match(r'^[a-zA-Z0-9\-]{1,63}$', v):
            raise ValueError("Hostname must be 1-63 characters: letters, digits, hyphens only")
        return v

class InterfaceIPRequest(BaseModel):
    interface: str
    ip: str
    mask: str
    shutdown: bool = False

    @field_validator("interface")
    @classmethod
    def interface_must_be_valid(cls, v):
        v = v.strip()
        if not re.match(
            r'^(FastEthernet|GigabitEthernet|Serial|Loopback|Ethernet|Vlan)\d+(/\d+)?$',
            v, re.IGNORECASE
        ):
            raise ValueError("Invalid interface name. Examples: FastEthernet0/0, GigabitEthernet1/0")
        return v

    @field_validator("ip")
    @classmethod
    def ip_must_be_valid(cls, v):
        try:
            IPvAnyAddress(v)
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")
        return v

    @field_validator("mask")
    @classmethod
    def mask_must_be_valid(cls, v):
        valid_masks = {
            "255.255.255.255", "255.255.255.254", "255.255.255.252",
            "255.255.255.248", "255.255.255.240", "255.255.255.224",
            "255.255.255.192", "255.255.255.128", "255.255.255.0",
            "255.255.254.0",   "255.255.252.0",   "255.255.248.0",
            "255.255.240.0",   "255.255.224.0",   "255.255.192.0",
            "255.255.128.0",   "255.255.0.0",     "255.254.0.0",
            "255.252.0.0",     "255.248.0.0",     "255.240.0.0",
            "255.224.0.0",     "255.192.0.0",     "255.128.0.0",
            "255.0.0.0",       "254.0.0.0",       "252.0.0.0",
            "248.0.0.0",       "240.0.0.0",       "224.0.0.0",
            "192.0.0.0",       "128.0.0.0",       "0.0.0.0",
        }
        if v not in valid_masks:
            raise ValueError(f"Invalid subnet mask: {v}")
        return v

class StaticRouteRequest(BaseModel):
    network: str
    mask: str
    next_hop: str

    @field_validator("network", "next_hop")
    @classmethod
    def must_be_valid_ip(cls, v):
        try:
            IPvAnyAddress(v)
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")
        return v

    @field_validator("mask")
    @classmethod
    def mask_must_be_valid(cls, v):
        try:
            IPvAnyAddress(v)
        except ValueError:
            raise ValueError(f"Invalid subnet mask: {v}")
        return v

class DeleteRouteRequest(BaseModel):
    network: str
    mask: str
    next_hop: str

    @field_validator("network", "next_hop", "mask")
    @classmethod
    def must_be_valid_ip(cls, v):
        try:
            IPvAnyAddress(v)
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")
        return v

class BannerRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def banner_must_be_safe(cls, v):
        forbidden = ['#', '\n', '\r', '\x00', '\x1b']
        for char in forbidden:
            if char in v:
                raise ValueError("Banner cannot contain: #, newlines, or control characters")
        if len(v) > 500:
            raise ValueError("Banner message cannot exceed 500 characters")
        return v.strip()

class PasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_must_be_strong(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 64:
            raise ValueError("Password cannot exceed 64 characters")
        if any(c in v for c in ['"', "'", '\n', '\r', '\x00']):
            raise ValueError("Password contains invalid characters")
        return v

# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/{device_id}/config/hostname")
def set_hostname(
    request: Request,
    device_id: int,
    payload: HostnameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(OperatorPlus)
):
    """Change the router's hostname."""
    device = _get_device_or_404(device_id, current_user.id, db)
    try:
        with ssh_connect(device) as conn:
            _send_config(conn, [f"hostname {payload.hostname}"])
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/hostname",
            detail=f"hostname set to '{payload.hostname}'",
            status="success", ip_address=_get_client_ip(request)
        )
        return {"message": f"Hostname set to '{payload.hostname}'"}
    except HTTPException as e:
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/hostname",
            detail=f"attempted to set hostname to '{payload.hostname}'",
            status="failed", error=e.detail, ip_address=_get_client_ip(request)
        )
        raise


@router.post("/{device_id}/config/interface")
def configure_interface(
    request: Request,
    device_id: int,
    payload: InterfaceIPRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(OperatorPlus)
):
    """Set IP address on an interface and bring it up or down."""
    device = _get_device_or_404(device_id, current_user.id, db)
    commands = [
        f"interface {payload.interface}",
        f"ip address {payload.ip} {payload.mask}",
        "shutdown" if payload.shutdown else "no shutdown",
    ]
    state = "shutdown" if payload.shutdown else "up"
    try:
        with ssh_connect(device) as conn:
            _send_config(conn, commands)
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/interface",
            detail=f"{payload.interface} set to {payload.ip}/{payload.mask} — {state}",
            status="success", ip_address=_get_client_ip(request)
        )
        return {"message": f"{payload.interface} configured with {payload.ip}/{payload.mask} — {state}"}
    except HTTPException as e:
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/interface",
            detail=f"attempted to configure {payload.interface}",
            status="failed", error=e.detail, ip_address=_get_client_ip(request)
        )
        raise


@router.post("/{device_id}/config/interface/toggle")
def toggle_interface(
    request: Request,
    device_id: int,
    interface: str,
    shutdown: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(OperatorPlus)
):
    """Bring an interface up or down without changing its IP."""
    if not re.match(
        r'^(FastEthernet|GigabitEthernet|Serial|Loopback|Ethernet|Vlan)\d+(/\d+)?$',
        interface, re.IGNORECASE
    ):
        raise HTTPException(status_code=400, detail="Invalid interface name")

    device = _get_device_or_404(device_id, current_user.id, db)
    commands = [f"interface {interface}", "shutdown" if shutdown else "no shutdown"]
    state = "shutdown" if shutdown else "brought up"
    try:
        with ssh_connect(device) as conn:
            _send_config(conn, commands)
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/interface/toggle",
            detail=f"{interface} {state}",
            status="success", ip_address=_get_client_ip(request)
        )
        return {"message": f"{interface} {state}"}
    except HTTPException as e:
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/interface/toggle",
            detail=f"attempted to toggle {interface}",
            status="failed", error=e.detail, ip_address=_get_client_ip(request)
        )
        raise


@router.post("/{device_id}/config/route")
def add_static_route(
    request: Request,
    device_id: int,
    payload: StaticRouteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(OperatorPlus)
):
    """Add a static route to the routing table."""
    device = _get_device_or_404(device_id, current_user.id, db)
    try:
        with ssh_connect(device) as conn:
            _send_config(conn, [f"ip route {payload.network} {payload.mask} {payload.next_hop}"])
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/route/add",
            detail=f"added route {payload.network}/{payload.mask} via {payload.next_hop}",
            status="success", ip_address=_get_client_ip(request)
        )
        return {"message": f"Static route added: {payload.network}/{payload.mask} via {payload.next_hop}"}
    except HTTPException as e:
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/route/add",
            detail=f"attempted to add route {payload.network}/{payload.mask}",
            status="failed", error=e.detail, ip_address=_get_client_ip(request)
        )
        raise


@router.delete("/{device_id}/config/route")
def delete_static_route(
    request: Request,
    device_id: int,
    payload: DeleteRouteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(OperatorPlus)
):
    """Remove a static route from the routing table."""
    device = _get_device_or_404(device_id, current_user.id, db)
    try:
        with ssh_connect(device) as conn:
            _send_config(conn, [f"no ip route {payload.network} {payload.mask} {payload.next_hop}"])
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/route/delete",
            detail=f"deleted route {payload.network}/{payload.mask} via {payload.next_hop}",
            status="success", ip_address=_get_client_ip(request)
        )
        return {"message": f"Static route removed: {payload.network}/{payload.mask}"}
    except HTTPException as e:
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/route/delete",
            detail=f"attempted to delete route {payload.network}/{payload.mask}",
            status="failed", error=e.detail, ip_address=_get_client_ip(request)
        )
        raise


@router.post("/{device_id}/config/banner")
def set_banner(
    request: Request,
    device_id: int,
    payload: BannerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(OperatorPlus)
):
    """Set the MOTD banner on the router."""
    device = _get_device_or_404(device_id, current_user.id, db)
    try:
        with ssh_connect(device) as conn:
            _send_config(conn, [f"banner motd #{payload.message}#"])
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/banner",
            detail="MOTD banner updated",
            status="success", ip_address=_get_client_ip(request)
        )
        return {"message": "Banner updated"}
    except HTTPException as e:
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/banner",
            detail="attempted to update banner",
            status="failed", error=e.detail, ip_address=_get_client_ip(request)
        )
        raise


@router.post("/{device_id}/config/password")
def change_password(
    request: Request,
    device_id: int,
    payload: PasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(AdminOnly)
):
    """Change the enable secret password on the router."""
    device = _get_device_or_404(device_id, current_user.id, db)
    try:
        with ssh_connect(device) as conn:
            _send_config(conn, [f"enable secret {payload.new_password}"])
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/password",
            detail="enable secret changed",
            status="success", ip_address=_get_client_ip(request)
        )
        return {"message": "Enable secret updated"}
    except HTTPException as e:
        log_action(
            db=db, user_id=int(current_user.id), device_id=device_id,
            action="config/password",
            detail="attempted to change enable secret",
            status="failed", error=e.detail, ip_address=_get_client_ip(request)
        )
        raise
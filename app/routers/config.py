from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, IPvAnyAddress
from typing import Optional, Any
import re
from app.db.database import get_db
from app.db.models import Device, User
from app.services.ssh import get_connection
from app.dependencies import get_current_user

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

# ── Schemas with Validators ────────────────────────────────────────────────────

class HostnameRequest(BaseModel):
    hostname: str

    @field_validator("hostname")
    @classmethod
    def hostname_must_be_valid(cls, v):
        v = v.strip()
        # Cisco hostname: letters, digits, hyphens, max 63 chars
        if not re.match(r'^[a-zA-Z0-9\-]{1,63}$', v):
            raise ValueError(
                "Hostname must be 1-63 characters: letters, digits, hyphens only"
            )
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
        # Match Cisco interface names: FastEthernet0/0, GigabitEthernet1/0, etc.
        if not re.match(
            r'^(FastEthernet|GigabitEthernet|Serial|Loopback|Ethernet|Vlan)\d+(/\d+)?$',
            v, re.IGNORECASE
        ):
            raise ValueError(
                "Invalid interface name. Examples: FastEthernet0/0, GigabitEthernet1/0"
            )
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
        # Valid subnet masks only
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
        # Block characters that could break CLI command structure
        forbidden = ['#', '\n', '\r', '\x00', '\x1b']
        for char in forbidden:
            if char in v:
                raise ValueError(
                    "Banner cannot contain: #, newlines, or control characters"
                )
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
        # Block characters that could break CLI command structure
        if any(c in v for c in ['"', "'", '\n', '\r', '\x00']):
            raise ValueError("Password contains invalid characters")
        return v


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/{device_id}/config/hostname")
def set_hostname(
    device_id: int,
    payload: HostnameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change the router's hostname."""
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    try:
        _send_config(conn, [f"hostname {payload.hostname}"])
    finally:
        conn.disconnect()
    return {"message": f"Hostname set to '{payload.hostname}'"}


@router.post("/{device_id}/config/interface")
def configure_interface(
    device_id: int,
    payload: InterfaceIPRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set IP address on an interface and bring it up or down."""
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    commands = [
        f"interface {payload.interface}",
        f"ip address {payload.ip} {payload.mask}",
        "shutdown" if payload.shutdown else "no shutdown",
    ]
    try:
        _send_config(conn, commands)
    finally:
        conn.disconnect()
    state = "shutdown" if payload.shutdown else "up"
    return {
        "message": f"{payload.interface} configured with {payload.ip}/{payload.mask} — {state}"
    }


@router.post("/{device_id}/config/interface/toggle")
def toggle_interface(
    device_id: int,
    interface: str,
    shutdown: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bring an interface up or down without changing its IP."""
    # Validate interface name
    if not re.match(
        r'^(FastEthernet|GigabitEthernet|Serial|Loopback|Ethernet|Vlan)\d+(/\d+)?$',
        interface, re.IGNORECASE
    ):
        raise HTTPException(status_code=400, detail="Invalid interface name")

    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    commands = [
        f"interface {interface}",
        "shutdown" if shutdown else "no shutdown",
    ]
    try:
        _send_config(conn, commands)
    finally:
        conn.disconnect()
    state = "shutdown" if shutdown else "brought up"
    return {"message": f"{interface} {state}"}


@router.post("/{device_id}/config/route")
def add_static_route(
    device_id: int,
    payload: StaticRouteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a static route to the routing table."""
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    try:
        _send_config(conn, [
            f"ip route {payload.network} {payload.mask} {payload.next_hop}"
        ])
    finally:
        conn.disconnect()
    return {
        "message": f"Static route added: {payload.network}/{payload.mask} via {payload.next_hop}"
    }


@router.delete("/{device_id}/config/route")
def delete_static_route(
    device_id: int,
    payload: DeleteRouteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a static route from the routing table."""
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    try:
        _send_config(conn, [
            f"no ip route {payload.network} {payload.mask} {payload.next_hop}"
        ])
    finally:
        conn.disconnect()
    return {"message": f"Static route removed: {payload.network}/{payload.mask}"}


@router.post("/{device_id}/config/banner")
def set_banner(
    device_id: int,
    payload: BannerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set the MOTD banner on the router."""
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    try:
        _send_config(conn, [f"banner motd #{payload.message}#"])
    finally:
        conn.disconnect()
    return {"message": "Banner updated"}


@router.post("/{device_id}/config/password")
def change_password(
    device_id: int,
    payload: PasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change the enable secret password on the router."""
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_
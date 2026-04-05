from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.db.database import get_db
from app.db.models import Device, User
from app.services.ssh import get_connection
from app.dependencies import get_current_user

router = APIRouter(prefix="/devices", tags=["Config"])

# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_device_or_404(device_id: int, user_id: int, db: Session) -> Device:
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.owner_id == user_id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

def _send_config(conn, commands: list[str]) -> str:
    """
    Sends a list of config commands using Netmiko's send_config_set.
    This automatically handles 'configure terminal' and 'end'.
    """
    output = conn.send_config_set(commands)
    conn.save_config()  # write memory
    return output

# ── Schemas ────────────────────────────────────────────────────────────────────

class HostnameRequest(BaseModel):
    hostname: str

class InterfaceIPRequest(BaseModel):
    interface: str          # e.g. "FastEthernet0/0"
    ip: str                 # e.g. "192.168.1.1"
    mask: str               # e.g. "255.255.255.0"
    shutdown: bool = False  # True = shutdown, False = no shutdown

class StaticRouteRequest(BaseModel):
    network: str            # e.g. "10.0.0.0"
    mask: str               # e.g. "255.0.0.0"
    next_hop: str           # e.g. "192.168.1.254"

class DeleteRouteRequest(BaseModel):
    network: str
    mask: str
    next_hop: str

class BannerRequest(BaseModel):
    message: str

class PasswordRequest(BaseModel):
    new_password: str

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
    _send_config(conn, [f"hostname {payload.hostname}"])
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
    _send_config(conn, commands)
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
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)

    commands = [
        f"interface {interface}",
        "shutdown" if shutdown else "no shutdown",
    ]
    _send_config(conn, commands)
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
    _send_config(conn, [f"ip route {payload.network} {payload.mask} {payload.next_hop}"])
    conn.disconnect()
    return {"message": f"Static route added: {payload.network}/{payload.mask} via {payload.next_hop}"}

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
    _send_config(conn, [f"no ip route {payload.network} {payload.mask} {payload.next_hop}"])
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
    # Use # as delimiter — make sure message doesn't contain #
    if "#" in payload.message:
        raise HTTPException(status_code=400, detail="Banner message cannot contain '#'")
    _send_config(conn, [f"banner motd #{payload.message}#"])
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
    conn = get_connection(device)
    _send_config(conn, [f"enable secret {payload.new_password}"])
    conn.disconnect()
    return {"message": "Enable secret updated"}
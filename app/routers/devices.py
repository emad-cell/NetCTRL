from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Device, User
from app.schemas.device import DeviceCreate, DeviceOut, CommandRequest
from app.core.security import encrypt_secret
from app.services.ssh import get_connection
from app.services import router_commands
from app.dependencies import get_current_user

router = APIRouter(prefix="/devices", tags=["Devices"])

# ── CRUD ──────────────────────────────────────────────────

@router.post("/", response_model=DeviceOut, status_code=201)
def add_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    payload_data = payload.model_dump()
    payload_data["password"] = encrypt_secret(payload_data["password"])
    if payload_data.get("secret") is not None:
        payload_data["secret"] = encrypt_secret(payload_data["secret"])

    device = Device(**payload_data, owner_id=current_user.id)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device

@router.get("/", response_model=list[DeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Device).filter(Device.owner_id == current_user.id).all()

@router.delete("/{device_id}", status_code=204)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == current_user.id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()

# ── SSH Commands ───────────────────────────────────────────

def _get_device_or_404(device_id: int, user_id: int, db: Session) -> Device:
    device = db.query(Device).filter(Device.id == device_id, Device.owner_id == user_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

# @router.get("/{device_id}/interfaces")
# def get_interfaces(
#     device_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     device = _get_device_or_404(device_id, current_user.id, db)
#     conn = get_connection(device)
#     output = router_commands.get_interface_brief(conn)
#     conn.disconnect()
#     return {"output": output}

# @router.get("/{device_id}/routes")
# def get_routes(
#     device_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     device = _get_device_or_404(device_id, current_user.id, db)
#     conn = get_connection(device)
#     output = router_commands.get_routing_table(conn)
#     conn.disconnect()
#     return {"output": output}

# @router.get("/{device_id}/arp")
# def get_arp(
#     device_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     device = _get_device_or_404(device_id, current_user.id, db)
#     conn = get_connection(device)
#     output = router_commands.get_arp_table(conn)
#     conn.disconnect()
#     return {"output": output}

# @router.get("/{device_id}/config")
# def get_config(
#     device_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     device = _get_device_or_404(device_id, current_user.id, db)
#     conn = get_connection(device)
#     output = router_commands.get_running_config(conn)
#     conn.disconnect()
#     return {"output": output}
from app.services import router_commands

@router.get("/{device_id}/interfaces", response_model=list)
def get_interfaces(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    data = router_commands.get_interfaces(conn)
    conn.disconnect()
    # Returns a list of Interface objects, not raw text output.
    return [i.model_dump() for i in data]

@router.get("/{device_id}/routes", response_model=list)
def get_routes(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    data = router_commands.get_routes(conn)
    conn.disconnect()
    return [r.model_dump() for r in data]

@router.get("/{device_id}/arp", response_model=list)
def get_arp(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    data = router_commands.get_arp(conn)
    conn.disconnect()
    return [a.model_dump() for a in data]

@router.get("/{device_id}/config")
def get_config(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    data = router_commands.get_config(conn)
    conn.disconnect()
    return data.model_dump()

@router.post("/{device_id}/command")
def run_command(
    device_id: int,
    payload: CommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = _get_device_or_404(device_id, current_user.id, db)
    conn = get_connection(device)
    try:
        output = router_commands.send_raw_command(conn, payload.command)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.disconnect()
    return {"output": output}

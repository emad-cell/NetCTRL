from netmiko import BaseConnection
from app.services import parsers
from app.schemas.network import Interface, Route, ArpEntry, ConfigSection
from typing import List

# ── Raw output (internal use) ──────────────────────────────────────────────────

def _get_interface_brief_raw(conn: BaseConnection) -> str:
    return conn.send_command("show ip interface brief")

def _get_routing_table_raw(conn: BaseConnection) -> str:
    return conn.send_command("show ip route")

def _get_arp_table_raw(conn: BaseConnection) -> str:
    return conn.send_command("show arp")

def _get_running_config_raw(conn: BaseConnection) -> str:
    return conn.send_command("show running-config", read_timeout=30)

# ── Parsed output (used by API endpoints) ─────────────────────────────────────

def get_interfaces(conn: BaseConnection) -> List[Interface]:
    return parsers.parse_interface_brief(_get_interface_brief_raw(conn))

def get_routes(conn: BaseConnection) -> List[Route]:
    return parsers.parse_routing_table(_get_routing_table_raw(conn))

def get_arp(conn: BaseConnection) -> List[ArpEntry]:
    return parsers.parse_arp_table(_get_arp_table_raw(conn))

def get_config(conn: BaseConnection) -> ConfigSection:
    return parsers.parse_running_config(_get_running_config_raw(conn))

def send_raw_command(conn: BaseConnection, command: str) -> str:
    """Only show commands allowed — config changes go through dedicated endpoints."""
    if not command.strip().lower().startswith("show"):
        raise ValueError("Only 'show' commands are allowed via this endpoint.")
    return conn.send_command(command, read_timeout=30)
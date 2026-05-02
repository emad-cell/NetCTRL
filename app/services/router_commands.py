from netmiko import BaseConnection
from app.services import parsers
from app.schemas.network import Interface, Route, ArpEntry, ConfigSection
from typing import List

# ── Allowlist — only these show commands are permitted ─────────────────────────
# This prevents expensive commands like 'show tech-support' that can
# take 10+ minutes and crash the demo, and blocks any dangerous variants.

ALLOWED_SHOW_COMMANDS = {
    "show ip interface brief",
    "show ip route",
    "show arp",
    "show version",
    "show running-config",
    "show startup-config",
    "show interfaces",
    "show ip ospf neighbor",
    "show ip ospf database",
    "show ip bgp summary",
    "show ip bgp",
    "show ip nat translations",
    "show ip nat statistics",
    "show cdp neighbors",
    "show cdp neighbors detail",
    "show lldp neighbors",
    "show lldp neighbors detail",
    "show vlan",
    "show vlan brief",
    "show spanning-tree",
    "show mac address-table",
    "show ip dhcp binding",
    "show ip dhcp pool",
    "show crypto isakmp sa",
    "show crypto ipsec sa",
    "show processes cpu",
    "show processes memory",
    "show logging",
    "show clock",
    "show users",
    "show line",
}

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
    """
    Execute a show command on the device.
    Only commands in ALLOWED_SHOW_COMMANDS are permitted.
    This prevents expensive commands like 'show tech-support' and
    blocks any config commands from being sent through this endpoint.
    """
    cmd = command.strip().lower()

    # Block control characters and newlines — injection prevention
    if any(c in command for c in ['\n', '\r', '\x00', ';', '|']):
        raise ValueError("Command contains invalid characters.")

    # Check against allowlist
    if cmd not in ALLOWED_SHOW_COMMANDS:
        raise ValueError(
            f"Command not allowed: '{command}'. "
            f"Allowed commands: {sorted(ALLOWED_SHOW_COMMANDS)}"
        )

    return conn.send_command(command, read_timeout=30)
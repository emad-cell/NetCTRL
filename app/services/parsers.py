import re
from typing import List, Optional
from app.schemas.network import Interface, Route, ArpEntry, InterfaceDetail, ConfigSection

# ── Interface Brief Parser ─────────────────────────────────────────────────────

def parse_interface_brief(output: str) -> List[Interface]:
    """
    Parses: show ip interface brief
    Example line:
    FastEthernet0/0   192.168.1.1   YES NVRAM  up   up
    """
    interfaces = []
    # Skip the header line and empty lines
    lines = [l for l in output.splitlines() if l.strip() and not l.startswith("Interface")]

    for line in lines:
        # Split on 2+ spaces to handle variable spacing
        parts = re.split(r'\s{2,}', line.strip())
        if len(parts) < 6:
            # Try single space split as fallback
            parts = line.split()

        if len(parts) >= 6:
            interfaces.append(Interface(
                interface=parts[0],
                ip=parts[1] if parts[1] != "unassigned" else None,
                ok=parts[2],
                method=parts[3],
                status=parts[4],
                protocol=parts[5],
            ))

    return interfaces

# ── Routing Table Parser ───────────────────────────────────────────────────────

# Cisco route code meanings
ROUTE_CODES = {
    "C": "connected",
    "S": "static",
    "R": "RIP",
    "O": "OSPF",
    "D": "EIGRP",
    "B": "BGP",
    "i": "ISIS",
    "L": "local",
}

def parse_routing_table(output: str) -> List[Route]:
    """
    Parses: show ip route
    Handles connected, static, and dynamic routes.
    Example lines:
    C    192.168.1.0/24 is directly connected, FastEthernet0/0
    S    10.0.0.0/8 [1/0] via 192.168.1.254
    O    172.16.0.0/16 [110/2] via 192.168.1.1, FastEthernet0/0
    """
    routes = []

    # Match lines that start with a route code letter
    route_pattern = re.compile(
        r'^([CSRODBL\*iIEeNn][\s\*]*)\s+'  # protocol code
        r'(\d+\.\d+\.\d+\.\d+(?:/\d+)?)'    # network/mask
        r'(?:\s+\[[\d/]+\])?'                # optional metric [AD/metric]
        r'(?:\s+via\s+(\d+\.\d+\.\d+\.\d+))?'  # optional next-hop
        r'(?:.*?,\s*(\S+))?'                 # optional interface at end
        r'|is directly connected,\s*(\S+)',  # or directly connected
        re.MULTILINE
    )

    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("Codes") or line.startswith("Gateway"):
            continue

        # Get protocol code (first character)
        code_match = re.match(r'^([A-Z\*i])', line)
        if not code_match:
            continue

        code = code_match.group(1).upper()
        protocol = ROUTE_CODES.get(code, code)

        # Extract network
        net_match = re.search(r'(\d+\.\d+\.\d+\.\d+(?:/\d+)?)', line)
        if not net_match:
            continue
        network_full = net_match.group(1)
        if "/" in network_full:
            network, mask = network_full.split("/")
        else:
            network, mask = network_full, None

        # Extract next hop
        via_match = re.search(r'via\s+(\d+\.\d+\.\d+\.\d+)', line)
        next_hop = via_match.group(1) if via_match else None

        # Extract interface
        iface_match = re.search(r'connected,\s*(\S+)|via\s+\S+,\s*(\S+)|,\s*((?:Fast|Gigabit|Serial|Loopback)\S+)', line)
        interface = None
        if iface_match:
            interface = iface_match.group(1) or iface_match.group(2) or iface_match.group(3)

        # Extract metric
        metric_match = re.search(r'\[(\d+/\d+)\]', line)
        metric = metric_match.group(1) if metric_match else None

        routes.append(Route(
            protocol=protocol,
            network=network,
            mask=mask,
            next_hop=next_hop,
            interface=interface,
            metric=metric,
        ))

    return routes

# ── ARP Table Parser ───────────────────────────────────────────────────────────

def parse_arp_table(output: str) -> List[ArpEntry]:
    """
    Parses: show arp
    Example line:
    Internet  192.168.1.1   -   aabb.cc00.0100  ARPA  FastEthernet0/0
    """
    entries = []
    for line in output.splitlines():
        # Skip header and empty lines
        if not line.strip() or line.startswith("Protocol"):
            continue

        parts = line.split()
        if len(parts) >= 6:
            entries.append(ArpEntry(
                protocol=parts[0],
                ip=parts[1],
                age=parts[2] if parts[2] != "-" else None,
                mac=parts[3],
                type=parts[4],
                interface=parts[5],
            ))

    return entries

# ── Running Config Parser ──────────────────────────────────────────────────────

def parse_running_config(output: str) -> ConfigSection:
    """
    Parses key fields from: show running-config
    Extracts hostname and interface details.
    Full raw config is always included as fallback.
    """
    interfaces = []

    # Extract hostname
    hostname_match = re.search(r'^hostname\s+(\S+)', output, re.MULTILINE)
    hostname = hostname_match.group(1) if hostname_match else None

    # Extract interface blocks
    # Each block starts with "interface X" and ends before the next "interface" or "!"
    iface_blocks = re.split(r'\ninterface ', output)

    for block in iface_blocks[1:]:  # skip everything before first interface
        lines = block.strip().splitlines()
        if not lines:
            continue

        iface_name = lines[0].strip()
        ip = mask = None

        for l in lines[1:]:
            l = l.strip()
            ip_match = re.match(r'ip address (\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)', l)
            if ip_match:
                ip = ip_match.group(1)
                mask = ip_match.group(2)

        # Determine status from interface brief context (simplified)
        interfaces.append(InterfaceDetail(
            interface=iface_name,
            status="unknown",   # full status needs 'show interfaces' — not running-config
            protocol="unknown",
            ip=ip,
            mask=mask,
        ))

    return ConfigSection(
        hostname=hostname,
        interfaces=interfaces,
        raw=output,
    )

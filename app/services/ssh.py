from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from fastapi import HTTPException
from app.db.models import Device
from app.core.security import decrypt_secret
from contextlib import contextmanager
import os

# Path to SSH config that handles legacy Cisco IOS algorithms
# (diffie-hellman-group1-sha1, 3des-cbc, ssh-rsa)
SSH_CONFIG_FILE = os.path.expanduser("~/.ssh/config")


def get_connection(device: Device):
    """
    Creates and returns an active Netmiko SSH connection.
    Used when you need manual control over the connection lifecycle.

    The ~/.ssh/config file must contain entries for legacy devices:
        Host <device_ip>
            KexAlgorithms +diffie-hellman-group1-sha1
            HostKeyAlgorithms +ssh-rsa
            Ciphers +3des-cbc
    """
    try:
        password = decrypt_secret(device.password) or device.password
        secret = decrypt_secret(device.secret) if device.secret else None
        connection = ConnectHandler(
            device_type=device.device_type,
            host=device.host,
            port=device.port,
            username=device.username,
            password=password,
            secret=secret or password,
            conn_timeout=10,
            ssh_config_file=SSH_CONFIG_FILE,
        )
        connection.enable()
        return connection

    except NetmikoAuthenticationException:
        raise HTTPException(
            status_code=401,
            detail=f"SSH authentication failed for {device.host} — check username/password/secret"
        )
    except NetmikoTimeoutException:
        raise HTTPException(
            status_code=504,
            detail=f"Connection timed out: {device.host} — is the device reachable?"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SSH connection error: {str(e)}"
        )


@contextmanager
def ssh_connect(device: Device):
    """
    Context manager for SSH connections — guarantees disconnect
    even if an exception occurs inside the with block.

    Usage:
        with ssh_connect(device) as conn:
            output = conn.send_command("show ip route")

    This replaces the try/finally pattern in every endpoint:
        # Before
        conn = get_connection(device)
        try:
            data = router_commands.get_interfaces(conn)
        finally:
            conn.disconnect()

        # After
        with ssh_connect(device) as conn:
            data = router_commands.get_interfaces(conn)
    """
    conn = get_connection(device)   # raises HTTPException if connection fails
    try:
        yield conn                  # endpoint code runs here
    finally:
        conn.disconnect()           # always runs — even on exception
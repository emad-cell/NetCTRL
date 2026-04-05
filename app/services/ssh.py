from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from fastapi import HTTPException
from app.db.models import Device
from app.core.security import decrypt_secret
import os

# Path to SSH config that handles legacy Cisco IOS algorithms
# (diffie-hellman-group1-sha1, 3des-cbc, ssh-rsa)
SSH_CONFIG_FILE = os.path.expanduser("~/.ssh/config")

def get_connection(device: Device):
    """
    Creates and returns an active Netmiko SSH connection.
    
    We use ssh_config_file instead of passing algorithms directly
    because Netmiko delegates raw SSH params to Paramiko, which
    doesn't accept them as constructor arguments in this version.
    
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
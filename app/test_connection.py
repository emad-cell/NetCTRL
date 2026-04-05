from netmiko import ConnectHandler

router = {
    "device_type": "cisco_ios",
    "host": "192.168.122.10",
    "username": "admin",
    "password": "admin",
    "secret": "admin",
    "conn_timeout": 10,
    "ssh_config_file": "/home/emad/.ssh/config",
}

print("Connecting to router...")
conn = ConnectHandler(**router)
conn.enable()
print("Connected!\n")

output = conn.send_command("show ip interface brief")
print(output)

conn.disconnect()
print("\nDisconnected.")
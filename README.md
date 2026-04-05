# NetCTRL

NetCTRL is a FastAPI-based network device management API for authenticating users, storing device inventory, and managing router/switch configuration over SSH. It exposes both read-only network inspection endpoints and configuration actions for Cisco IOS-style devices through Netmiko.

## Features

- User registration, login, and protected profile access with JWT bearer tokens
- Device inventory management per user
- SSH connectivity to managed devices through Netmiko
- Read-only network queries for interfaces, routes, ARP tables, and running configuration
- Configuration actions for hostname, interface settings, static routes, banners, and enable secrets
- Encrypted device credentials at rest with Fernet
- Auto-generated API documentation with Swagger UI and ReDoc

## Tech Stack

- Python 3.10+
- FastAPI
- SQLAlchemy
- Netmiko
- Pydantic Settings
- python-jose and passlib
- cryptography

## Project Structure

```text
requirements.txt
run.py
app/
  main.py
  dependencies.py
  core/
  db/
  routers/
  schemas/
  services/
```

## Getting Started

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your environment file

Create a `.env` file in the project root:

```env
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///./netctrl.db
ACCESS_TOKEN_EXPIRE_MINUTES=60
# Optional. If omitted, the Fernet key is derived from SECRET_KEY.
FERNET_KEY=
# Legacy alias supported by the app for existing environments.
# ENCRYPTION_KEY=
```

### 4. Run the API

```bash
python run.py
```

The server starts on `http://0.0.0.0:8001`.

## API Documentation

- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## Main Endpoints

### Authentication

- `POST /auth/register` - Create a new user account
- `POST /auth/login` - Obtain a bearer token
- `GET /auth/me` - Return the authenticated user profile

### Devices

- `POST /devices/` - Add a managed device
- `GET /devices/` - List the current user's devices
- `DELETE /devices/{device_id}` - Remove a device
- `GET /devices/{device_id}/interfaces` - Show parsed interface status
- `GET /devices/{device_id}/routes` - Show parsed routing table entries
- `GET /devices/{device_id}/arp` - Show parsed ARP entries
- `GET /devices/{device_id}/config` - Return parsed running configuration
- `POST /devices/{device_id}/command` - Send an allowed `show` command

### Configuration

- `POST /devices/{device_id}/config/hostname` - Set the router hostname
- `POST /devices/{device_id}/config/interface` - Configure interface IP and state
- `POST /devices/{device_id}/config/interface/toggle` - Bring an interface up or down
- `POST /devices/{device_id}/config/route` - Add a static route
- `DELETE /devices/{device_id}/config/route` - Remove a static route
- `POST /devices/{device_id}/config/banner` - Set the MOTD banner
- `POST /devices/{device_id}/config/password` - Update the enable secret

## Security Notes

- User passwords are hashed with bcrypt.
- Device passwords and enable secrets are encrypted before being stored.
- SSH credentials are decrypted only when a connection is opened.
- The API uses JWT bearer authentication for protected routes.
- Legacy Cisco SSH algorithms can be configured through `~/.ssh/config` when required.

## Behavior Notes

- The application creates database tables on startup with SQLAlchemy metadata.
- The allowed raw command endpoint only permits `show` commands.
- CORS is configured for local frontend development at `http://localhost:3000`.

## Development

If you want to add tests or extend the API, keep network parsing logic in `app/services/` and request/response models in `app/schemas/`.

## License

Add your preferred license here if you plan to publish the project publicly.

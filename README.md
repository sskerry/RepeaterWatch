# RepeaterWatch

MeshCore repeater monitoring dashboard built with Python and Flask. Collects data from MeshCore devices via serial and displays real-time charts, neighbor maps, and system health in a web interface.

## Features

- Real-time radio statistics (SNR, RSSI, airtime, packets)
- Neighbor map with SNR-colored polylines
- Raspberry Pi system monitoring (CPU, memory, disk, temperature)
- Environmental sensor support (INA3221, BME280, AS3935, BQ24074, LIS2DW12)
- Remote firmware flashing (nRF52 DFU over USB)
- Serial terminal via WebSocket
- GPIO radio reset and USB relay control
- Dark/light theme with mobile-responsive layout
- Authentication with bcrypt password hashing
- CSRF protection on all write endpoints
- Fail2ban-style login brute force protection
- Reverse proxy support with trusted proxy validation

## Quick Install

The installer sets up the full stack: SerialMux, mctomqtt, and RepeaterWatch.

```bash
sudo bash install.sh
```

It will prompt for your serial port, hardware name, web port, and which repo to use.

## Upgrade

Upgrade an existing installation from any fork while preserving your `.env` and database:

```bash
sudo bash upgrade.sh
```

## Manual Setup

If you prefer to install manually, see the systemd service file in `systemd/meshcore-monitor.service`. The service runs as root (required for GPIO access, terminal, and service management).

### Password Management

Set or change the dashboard password:

```bash
sudo /opt/RepeaterWatch/venv/bin/python3 setup_auth.py
sudo systemctl restart RepeaterWatch
```

Or manage authentication from the Settings tab in the web dashboard.

## Contributors

- [MrAlders0n](https://github.com/MrAlders0n) - Original author
- [jjkroell](https://github.com/jjkroell) (VE7KOD) - UX overhaul, dark/light theme, mobile layout, sensor management, install/uninstall scripts
- [sskerry](https://github.com/sskerry) (MYCALL) - Security hardening (CSRF, fail2ban, session hardening, auth management), upgrade script, bug fixes

## License

See [LICENSE](LICENSE) for details.

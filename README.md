# RepeaterWatch

A web-based monitoring dashboard for [MeshCore](https://meshcore.net/) repeaters, built with Python and Flask. Designed to run on a Raspberry Pi alongside your MeshCore radio, providing real-time statistics, neighbor tracking, and remote management through a browser.

> **WARNING: This software is provided as-is, with no warranty of any kind. Use at your own risk.**
> RepeaterWatch provides remote access to your Raspberry Pi including a full shell terminal,
> firmware flashing, GPIO control, and system reboot. Misconfiguration or unauthorized access
> could result in damage to your hardware, loss of data, or unintended radio transmissions.
> You are solely responsible for securing your deployment.

## Features

### Radio Monitoring
- Real-time SNR, RSSI, noise floor, and airtime utilization charts
- Packet tracking (direct/flood) with duplicate detection
- Neighbor map with SNR-colored polylines and distance calculations
- Neighbor table with signal history and averages
- Radio configuration display (frequency, bandwidth, spreading factor)

### System Health
- Raspberry Pi CPU, memory, disk, and temperature monitoring
- Per-process resource usage (top processes)
- Disk I/O tracking
- Service status monitoring (SerialMux, mctomqtt, RepeaterWatch)

### Environmental Sensors
- **INA3221** — 3-channel voltage/current/power monitor (solar, battery, load)
- **BME280** — Temperature, humidity, barometric pressure
- **AS3935** — Lightning detection with configurable sensitivity
- **BQ24074** — Battery charge controller status and control
- **LIS2DW12** — Accelerometer (vibration/tilt monitoring)
- Toggle sensors on/off from the dashboard without editing config files

### Remote Management
- Serial terminal via WebSocket (full shell access)
- Remote firmware flashing (nRF52 DFU over USB)
- GPIO radio reset and bootloader mode
- USB relay control (for external power switching)
- System reboot
- Database reset and neighbor management
- Service restart

### Security
- Password authentication with bcrypt hashing
- CSRF protection on all write endpoints
- Fail2ban-style IP lockout for brute force protection
- Session cookie hardening (HttpOnly, SameSite, Secure)
- Reverse proxy support with trusted proxy IP validation
- Sensitive info redacted for unauthenticated users
- Dangerous endpoints locked down until password is set (unless local mode is enabled)

### UI/UX
- Dark and light theme with auto-detection
- Mobile-responsive layout (works on phones, tablets, desktops)
- DM Sans + JetBrains Mono typography
- Tabbed interface: MeshCore, Raspberry Pi, Sensors, Tools, Settings
- Password management from the Settings page (no CLI needed)

## Requirements

- **Raspberry Pi** (tested on Pi 4 and Compute Module 3) running **Raspberry Pi OS 64-bit** (Bookworm or newer)
- **MeshCore radio** connected via USB (e.g., Ikoka Stick, Heltec T114, RAK 4631)
- **Python 3.10+**
- **SerialMux** for sharing the serial port between RepeaterWatch, mctomqtt, and the terminal

## Quick Install

The installer handles everything on a **fresh Raspberry Pi OS 64-bit install**: system packages, I2C setup, SerialMux, mctomqtt, and RepeaterWatch.

```bash
curl -fsSL https://raw.githubusercontent.com/sskerry/RepeaterWatch/main/install.sh | sudo bash
```

Or clone and run locally:

```bash
git clone https://github.com/sskerry/RepeaterWatch.git /opt/RepeaterWatch
cd /opt/RepeaterWatch
sudo bash install.sh
```

The installer will prompt you for:
1. **Serial port** — auto-detected if only one USB device is connected
2. **Hardware name** — description of your radio (e.g., "Ikoka Stick 30dB")
3. **Web port** — default 5000
4. **Repository** — choose upstream, sskerry, jjkroell, or a custom URL
5. **Access mode** — set a password or enable local mode for trusted LANs

## Upgrade

Upgrade an existing installation from any fork. Your `.env` config and database are preserved.

```bash
cd /opt/RepeaterWatch
sudo bash upgrade.sh
```

The upgrade script will:
- Back up your database and config
- Let you choose the target repo (upstream, sskerry, jjkroell, or custom)
- Replace all code files
- Install any new Python dependencies
- Add new `.env` settings without overwriting existing ones
- Migrate old `meshcoremon` user installs to root
- Restart the service

## Uninstall

Completely removes RepeaterWatch, mctomqtt, and SerialMux with an optional database backup.

```bash
cd /opt/RepeaterWatch
sudo bash uninstall.sh
```

## Access Modes

RepeaterWatch has three access modes, depending on your deployment:

### Local Mode (trusted LAN)
Set `MESHCORE_LOCAL_MODE=1` in `.env`. All features are accessible without a password. A warning banner is displayed on the dashboard.

> **WARNING:** Local mode grants full access to the terminal, firmware flashing, GPIO, and system
> reboot to anyone who can reach the dashboard. Only use this on networks you fully control.
> Never enable local mode on internet-facing installs.

### Password Protected (recommended for remote access)
Set a password via the Settings page or CLI:
```bash
sudo /opt/RepeaterWatch/venv/bin/python3 setup_auth.py
sudo systemctl restart RepeaterWatch
```

The dashboard is publicly readable (charts, neighbors, status), but all write operations and dangerous endpoints require authentication.

### Locked Down (no password, no local mode)
The default. The dashboard is read-only. Dangerous endpoints (terminal, reboot, flash, GPIO) are completely blocked until either a password is set or local mode is enabled.

## Configuration

All settings are in `/opt/RepeaterWatch/.env`. See `.env.example` for the full list with descriptions.

Key settings:
| Variable | Default | Description |
|----------|---------|-------------|
| `MESHCORE_SERIAL_PORT` | `/dev/ttyV0` | Serial port (via SerialMux) |
| `MESHCORE_POLL_INTERVAL` | `300` | Stats polling interval (seconds) |
| `MESHCORE_PORT` | `5000` | Web dashboard port |
| `MESHCORE_LOCAL_MODE` | `0` | Enable local mode (no auth required) |
| `MESHCORE_SENSOR_POLL` | `0` | Enable/disable all sensor polling |
| `MESHCORE_RADIO_RESET_GPIO` | `4` | GPIO pin for radio reset |
| `MESHCORE_USB_RELAY_GPIO` | `17` | GPIO pin for USB relay |

## Security Considerations

> **WARNING:** RepeaterWatch provides a full shell terminal, firmware flashing, and GPIO control.
> If exposed to the internet without proper security, an attacker could:
> - Execute arbitrary commands on your Raspberry Pi
> - Flash malicious firmware to your radio
> - Reboot or damage your hardware
> - Access your local network

**If exposing to the internet:**
1. **Always use HTTPS** via a reverse proxy (nginx, Caddy, etc.)
2. **Set a strong password** — bcrypt-hashed, minimum 8 characters
3. **Configure trusted proxies** — set `MESHCORE_TRUSTED_PROXIES` to your proxy's IP
4. **Never enable local mode** on internet-facing installs
5. **Keep the system updated** — `sudo apt update && sudo apt upgrade`

## Architecture

```
USB Radio ──> SerialMux ──┬──> /dev/ttyV0 ──> RepeaterWatch (monitoring + web UI)
                          ├──> /dev/ttyV1 ──> mctomqtt (MQTT bridge)
                          └──> /dev/ttyV2 ──> Terminal (serial console)
```

- `app.py` — Flask application entry point
- `collector/stats_poller.py` — Polls radio stats + Pi health on a schedule
- `collector/serial_reader.py` — Serial communication with MeshCore device
- `collector/sensor_poller.py` — Environmental sensor polling
- `collector/firmware_flasher.py` — nRF52 DFU firmware flash pipeline
- `collector/radio_gpio.py` — GPIO reset and bootloader control
- `api/routes.py` — REST API endpoints (`/api/v1/`)
- `api/terminal.py` — WebSocket terminal backend
- `database/` — SQLite storage (no ORM)
- `config.py` — Environment variable configuration
- `static/` — CSS, JavaScript, chart libraries
- `templates/` — Jinja2 HTML templates

## Useful Commands

```bash
# Service management
sudo systemctl status RepeaterWatch
sudo systemctl restart RepeaterWatch
sudo journalctl -u RepeaterWatch -f

# Password management
sudo /opt/RepeaterWatch/venv/bin/python3 /opt/RepeaterWatch/setup_auth.py
sudo /opt/RepeaterWatch/venv/bin/python3 /opt/RepeaterWatch/setup_auth.py --clear

# View logs for all services
sudo journalctl -u SerialMux -u mctomqtt -u RepeaterWatch -f
```

## Contributors

- [MrAlders0n](https://github.com/MrAlders0n) — Original author
- [jjkroell](https://github.com/jjkroell) (VE7KOD) — UX overhaul: dark/light theme, mobile layout, sensor management modal, neighbor map improvements, install/uninstall scripts
- [sskerry](https://github.com/sskerry) (MYCALL) — Security hardening: CSRF protection, fail2ban, session hardening, auth management UI, local mode, upgrade script, bug fixes

## License

See [LICENSE](LICENSE) for details.

---

> **Disclaimer:** This software is not affiliated with or endorsed by MeshCore. Use at your own risk.
> The authors are not responsible for any damage to hardware, data loss, or unintended radio
> transmissions resulting from the use of this software. Always comply with local radio regulations.

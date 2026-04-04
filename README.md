# RepeaterWatch

A web-based monitoring dashboard for [MeshCore](https://meshcore.net/) repeaters. Runs on a Raspberry Pi alongside your radio, providing real-time stats, neighbor tracking, and remote management.

> **This software is provided as-is with no warranty. Use at your own risk.**
> RepeaterWatch provides shell access, firmware flashing, GPIO control, and system reboot.
> You are responsible for securing your deployment.

## Features

- Real-time radio charts (SNR, RSSI, noise floor, airtime, packets)
- Neighbor map with SNR-colored polylines and signal history
- Raspberry Pi health monitoring (CPU, memory, disk, temperature)
- Environmental sensors (INA3221, BME280, AS3935, BQ24074, LIS2DW12) — toggleable from the dashboard
- Serial terminal via WebSocket
- Remote firmware flashing (nRF52 DFU)
- GPIO radio reset, bootloader mode, and USB relay control
- Dark/light theme, mobile-responsive layout
- Authentication with bcrypt, CSRF protection, fail2ban-style lockout
- No-password mode: skip auth setup for trusted LANs, set a password anytime

## Requirements

- Raspberry Pi (tested on Pi 4 and CM3) with **Raspberry Pi OS 64-bit**
- MeshCore radio via USB (Ikoka Stick, Heltec T114, RAK 4631, etc.)
- Python 3.10+

## Install / Upgrade / Uninstall

```bash
# Fresh install (handles everything on a blank Pi)
curl -fsSL https://raw.githubusercontent.com/sskerry/RepeaterWatch/main/install.sh | sudo bash

# Upgrade from any fork (preserves .env and database)
cd /opt/RepeaterWatch && sudo bash upgrade.sh

# Full removal with optional database backup
cd /opt/RepeaterWatch && sudo bash uninstall.sh
```

## Access Modes

| Mode | Config | Behavior |
|------|--------|----------|
| **Open** (default) | No password set | All features accessible without login. **Trusted LANs only.** |
| **Password protected** | Set via Settings page or `setup_auth.py` | Dashboard is read-only for visitors. Write operations require login. |

## GPIO Pin Reference

All pins use BCM numbering and are configurable via `.env`:

| Function | ENV Variable | Default | Notes |
|----------|-------------|---------|-------|
| Radio reset | `MESHCORE_RADIO_RESET_GPIO` | 4 | Directly connected to radio RESET pin |
| USB relay | `MESHCORE_USB_RELAY_GPIO` | 17 | Controls VBUS on USB cable to radio (see below) |
| AS3935 IRQ | `MESHCORE_AS3935_IRQ_GPIO` | 18 | Lightning detector interrupt |
| BQ24074 /CHG | `MESHCORE_BQ24074_CHG_GPIO` | 19 | Charge status (active low) |
| BQ24074 /PGOOD | `MESHCORE_BQ24074_PGOOD_GPIO` | 13 | Power good (active low) |
| BQ24074 CE | `MESHCORE_BQ24074_CE_GPIO` | 6 | Charge enable |

I2C sensors (BME280, INA3221) use the Pi's fixed I2C pins (GPIO 2/3, physical pins 3/5).

### USB Relay

The USB relay controls the VBUS (5V power) line on the USB cable between the Pi and the radio. USB data lines (D+/D-) remain connected at all times, so serial communication works regardless of relay state.

**Why?** Many MeshCore radio boards have an onboard charger that activates when USB power is present. If you're using an external charge controller (like the BQ24074), you want VBUS disconnected during normal operation so the external charger manages the battery. The relay lets you cut VBUS for normal use and reconnect it only when needed for DFU firmware flashing (which requires the radio to detect a USB host).

The relay is wired NO/COM (normally open) — relay off = VBUS disconnected = external charger in control. Not required for basic operation.

## Configuration

All settings in `/opt/RepeaterWatch/.env`. See [.env.example](.env.example) for the full list.

## Architecture

```
USB Radio ──> SerialMux ──┬──> /dev/ttyV0 ──> RepeaterWatch (web UI + monitoring)
                          ├──> /dev/ttyV1 ──> mctomqtt (MQTT bridge)
                          └──> /dev/ttyV2 ──> Terminal (serial console)
```

## Security

If exposing to the internet: use HTTPS (reverse proxy), set a strong password, and configure `MESHCORE_TRUSTED_PROXIES`. See the Settings tab in the dashboard for security notes.

## Contributors

- [MrAlders0n](https://github.com/MrAlders0n) — Original author
- [jjkroell](https://github.com/jjkroell) (VE7KOD) — UX overhaul, dark/light theme, mobile layout, sensor management, install/uninstall scripts
- [sskerry](https://github.com/sskerry) (MYCALL) — Security hardening, CSRF, fail2ban, upgrade script, bug fixes

## License

See [LICENSE](LICENSE). Not affiliated with or endorsed by MeshCore. Always comply with local radio regulations.

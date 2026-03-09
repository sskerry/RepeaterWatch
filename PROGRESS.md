# RepeaterWatch — Project Progress

**Owner:** MYCALL (representing CLUB1 and CLUB2)
**Hardware target:** Raspberry Pi 4 + Ikoka stick MeshCore device
**Last updated:** 2026-03-09

---

## Goals & Status

| # | Goal | Status |
|---|------|--------|
| 0 | Git/GitHub setup | ✅ Done — private repo, SSH keys, remotes configured |
| 1 | Understand the codebase | ✅ Done — see notes below |
| 2 | Clean install documentation | ✅ Done — docs/INSTALL.md written and validated |
| 3 | Get it running on repeater hardware | ✅ Done on home Pi — all three services running |
| 4 | Explore sensors and GPIO | 🔄 In progress — GPIO wiring doc created, reset pin confirmed |
| 5 | Customize for CLUB1 / CLUB2 | ⬜ Not started |
| 6 | Maintain clean upstream upgrade path | ⬜ Ongoing consideration |

---

## Current Focus

**Goal 4 — Wire GPIO reset pin on home Pi, then prepare for mountain Pi deployment**

INSTALL.md is complete and validated. Update workflow documented.
Next: wire Pi GPIO 4 → Ikoka RESET pad, test remote reset from dashboard.

---

## Session Notes

### Session 1 — 2026-03-07
- Did a full codebase read-through and explanation
- Learned how the project works: serial reader → stats poller → SQLite → Flask API → dashboard
- Identified key config settings needed for Ikoka stick setup
- Drafted a step-by-step install guide (in chat — needs to be turned into a standalone doc)
- Set up Git identity: sskerry <user@example.com>
- Generated SSH key and added to GitHub account (sskerry)
- Created new **private** GitHub repo (sskerry/RepeaterWatch) — old public fork deleted
- Remotes configured: `origin` = private repo, `upstream` = MrAlders0n/RepeaterWatch

### Session 2 — 2026-03-07
- Discussed how Claude Code memory/context works across sessions
- Moved memory file from `~/.claude/` (local only) to Nextcloud for cross-machine sync
- Updated `CLAUDE.md` to reference new memory path
- Generated SSH key pair for Claude Code Pi access — stored in `~/.ssh/`
- Created `claude` user on home Pi with passwordless sudo
- Discovered home Pi OS is **Debian 13 (trixie)**, not Raspberry Pi OS
- Confirmed Ikoka stick serial port is `/dev/ttyACM0` (CDC ACM device, not ttyUSB0)
- Confirmed Seeed Studio XIAO nRF52840 = the Ikoka stick's processor
- Discovered mctomqtt (letsmesh) is already running and holds the serial port exclusively
- **Decision reversed:** SerialMux IS needed — mctomqtt and RepeaterWatch must share the port
- Confirmed mctomqtt config lives at `/etc/mctomqtt/config.toml` + `/etc/mctomqtt/config.d/00-user.toml`
- Confirmed mctomqtt uses `/dev/serial/by-id/usb-Seeed_Studio_XIAO_nRF52840_85A0C3E1D8C354BB-if00`
- Local MQTT broker at LOCAL_IP no longer needed (was for testing, mctomqtt handles cloud publish)
- Confirmed RepeaterWatch has full GPIO reset/DFU/firmware flash capability in the codebase
- Created `docs/gpio-wiring.md` — pin reference for Pi 4 + Ikoka stick
- Confirmed RESET pin is accessible on the Ikoka stick
- USB relay circuit (GPIO 17) needs clarification from original developer (MrAlders0n)
- Ikoka stick has custom firmware with packet logging enabled — required for serial data output

### Session 4 — 2026-03-09

- Confirmed all GPIO pins are configurable via `.env` (see pin summary below)
- Confirmed BME280 (temp/humidity/pressure) and INA3221 (3-channel current/voltage) are both I2C — no GPIO pins needed
- INA3221 channels: ch0 = battery, ch1 = load, ch2 = solar; polled every 10s
- BME280 polled every 60s; uses I2C address 0x77 — note: some cheap modules default to 0x76
- Added Note 3 (BME280) and Note 4 (INA3221) to `docs/gpio-wiring.md`
- Added I2C sensor table to the gpio-wiring doc pin map section
- Full pin summary: I2C bus on Pi pins 3+5 (GPIO2/3); GPIO pins 4, 6, 13, 17, 18, 19 for reset/relay/sensors
- All sensor polling disabled globally with `MESHCORE_SENSOR_POLL=0`; individual sensors silently skip if library not installed

### Session 3 (continued) — 2026-03-08
- Found SerialMux repo: https://github.com/MrAlders0n/SerialMux — single Python script, MIT license
- Installed SerialMux at `/opt/SerialMux/` with its own Python venv
- Wrote systemd service file for SerialMux (not included in the repo) — runs as root
- SerialMux running, virtual ports confirmed: `/dev/ttyV0`, `/dev/ttyV1`, `/dev/ttyV2`
- Reconfigured mctomqtt to use `/dev/ttyV1` (was raw serial by-id path)
- Installed RepeaterWatch to `/opt/RepeaterWatch/` via rsync from Mac
- Created `meshcoremon` system user (no shell, no home directory)
- Set up Python 3.13 venv — note: lgpio requires manual symlink on Debian 13 trixie (see install notes)
- Created `/etc/sudoers.d/meshcoremon` for firmware flash service control
- Created `.env` with correct settings (ttyV0 for RepeaterWatch, ttyV2 for terminal, sensor poll disabled)
- Auth disabled by commenting out `MESHCORE_PASSWORD` in `.env`
- Installed and started `meshcore-monitor` systemd service — depends on SerialMux
- **RepeaterWatch is live at http://PI_IP:5000 and reading real device data**
- Device confirmed: Ikoka Stick-E22-30dBm (Xiao_nrf52), firmware 1.13.0-letsmesh.net
- Harmless warning: `stats-extpower` command not supported by this firmware — can be ignored
- Fixed two bugs: service must be named `RepeaterWatch` exactly; must run as root (no User= line)
- Pi web terminal and service status page now working correctly
- INSTALL.md written, committed, pushed — full validated install guide in docs/
- Discussed update workflow (upstream → Mac → Pi) — documented in INSTALL.md and MEMORY.md
- Discussed compatibility: works with any nRF52840 MeshCore device; ESP32 monitoring works but flash/reset needs new code
- Identified ESP32 support as a future upstream contribution
- Clarified contribution workflow: private repo requires a temporary public fork for PRs
- No plans to customize core files — upstream updates will be conflict-free

---

## Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-07 | ~~Skip SerialMux~~ → **USE SerialMux** | mctomqtt (letsmesh) already runs on the Pi and holds the serial port; SerialMux lets both services share it |
| 2026-03-07 | Disable sensor polling initially | No sensor hardware on hand yet |
| 2026-03-07 | Use home Pi (meshcore-site1) as test bed | Low-stakes production deployment, safe to experiment on |
| 2026-03-07 | Store Claude SSH key in Nextcloud | Allows Claude Code access from any Mac without re-setup |
| 2026-03-08 | Run SerialMux as root | Needs to create /dev symlinks; standard for hardware daemons |
| 2026-03-08 | Disable auth (comment out MESHCORE_PASSWORD) | Home Pi is on a trusted local network |

---

## Open Questions

- Will the Pi have internet access at the mountain repeater site for initial setup?
- What network/IP scheme is used at the site — how will the dashboard be accessed remotely?
- USB relay circuit (GPIO 17): what is it switching, is it necessary, and how is it wired? (ask MrAlders0n)
- What OS image will be used on the mountain Pi? (use Debian 13 trixie to match home Pi)

---

## Install Checklist (home Pi — meshcore-site1)

- [x] Pi running Debian 13 (trixie)
- [x] SSH enabled
- [x] mctomqtt (letsmesh) installed and running
- [x] Ikoka stick connected at `/dev/ttyACM0`
- [x] `claude` user created with passwordless sudo
- [x] SerialMux installed at `/opt/SerialMux/`, systemd service running
- [x] mctomqtt reconfigured to use `/dev/ttyV1`
- [x] RepeaterWatch installed at `/opt/RepeaterWatch/`
- [x] `meshcoremon` system user created
- [x] Python venv created, dependencies installed, lgpio symlinked
- [x] `/etc/sudoers.d/meshcoremon` created
- [x] `.env` file configured (ttyV0, sensor poll off, auth disabled)
- [x] `meshcore-monitor` systemd service installed, enabled, running
- [x] Dashboard live at http://PI_IP:5000 — reading real device data
- [ ] Wire GPIO 4 → Ikoka RESET pin and test remote reset from dashboard
- [ ] Write up full install process as `docs/INSTALL.md`

---

## SerialMux Port Assignments (home Pi)

| Virtual Port | Assigned To | Purpose |
|---|---|---|
| `/dev/ttyV0` | RepeaterWatch | Main data polling |
| `/dev/ttyV1` | mctomqtt | LetsMesh cloud relay |
| `/dev/ttyV2` | RepeaterWatch terminal | Web terminal feature |

---

## Notes on Upstream Updates

**MYCALL's repo (private):** `https://github.com/sskerry/RepeaterWatch`
**Upstream (original, public):** `https://github.com/MrAlders0n/RepeaterWatch` — tracked as a Git remote called `upstream`.

To pull future upstream changes without losing local work:
```bash
git fetch upstream
git merge upstream/main
```

Files most likely to conflict with customizations:
- `templates/index.html` (dashboard HTML)
- `static/css/dashboard.css` (styling)
- `config.py` (if we add new config options)

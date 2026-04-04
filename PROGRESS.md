# RepeaterWatch — Project Progress

**Owner:** MYCALL (representing CLUB1 and CLUB2)
**Hardware target:** Raspberry Pi + Ikoka stick MeshCore device
**Last updated:** 2026-04-04

---

## Goals & Status

| # | Goal | Status |
|---|------|--------|
| 0 | Git/GitHub setup | ✅ Done — public fork (sskerry/RepeaterWatch), upstream remote |
| 1 | Understand the codebase | ✅ Done |
| 2 | Clean install documentation | ✅ Done — docs/INSTALL.md + install.sh automated installer |
| 3 | Get it running on repeater hardware | ✅ 3 Pis deployed (home, MRP, Hatzic West) |
| 4 | Explore sensors and GPIO | ✅ BQ24074 charger working on Hatzic. GPIO wiring doc complete |
| 5 | Customize for CLUB1 / CLUB2 | ⬜ Not started |
| 6 | Maintain clean upstream upgrade path | ✅ Ongoing — no core file customizations |

---

## Current Focus

**Hatzic West Pi deployed, RS232 bridge firmware build in progress**

Three Pis fully deployed and operational. Hatzic West (Nebra conversion) needs custom
MeshCore firmware with RS232 bridge to use UART instead of USB serial (VBUS required for
USB enumeration, relay cuts VBUS by design). Sensor poller bug found — needs fix.

---

## Open Work Items

### Bug: Sensor poller ignores individual enable/disable flags
- **File:** `collector/sensor_poller.py`
- **Problem:** When `MESHCORE_SENSOR_POLL=1`, ALL sensors are polled every tick regardless of individual `MESHCORE_SENSOR_*=0` flags. The individual flags are only used by the Settings UI toggles, never checked by the poller.
- **Symptom:** LIS2DW12 throws I2C errors every 5 seconds even though `MESHCORE_SENSOR_LIS2DW12=0`
- **Fix:** Add `config.SENSOR_*_ENABLED` flags to `config.py` (read from env), check them in `_run_loop()` before calling each `_poll_*` method. Also update startup log to distinguish "disabled" vs "library missing".
- **Affected sensors:** All five (INA3221, BME280, LIS2DW12, AS3935, BQ24074)

### Hatzic West: RS232 bridge firmware
- **Status:** Briefing created at `~/Nextcloud/claude/meshcore-rs232/CLAUDE.md`
- **Goal:** Build Ikoka Stick repeater firmware with RS232 bridge (UART on D6/D7)
- **Why:** Relay cuts VBUS, nRF52840 needs VBUS for USB — UART bypasses this entirely
- **Wiring:** Already done (D6→Pi Pin 10, D7→Pi Pin 8, GND→Pin 14)
- **After flash:** Enable bridge, switch SerialMux REAL_PORT from ttyACM0 to ttyAMA0

### Hatzic West: USB relay wiring
- **Current:** NO (normally open) — VBUS cut by default, stick doesn't enumerate
- **Workaround:** gpioset holds GPIO 17 high (dies on reboot)
- **If RS232 firmware works:** Relay stays as-is (VBUS only needed for flashing)
- **If RS232 firmware doesn't work:** Swap relay from NO to NC (one wire move)

### Update gpio-wiring.md with confirmed findings
- VBUS IS required for nRF52840 USB enumeration — update Note 2 to mark as CONFIRMED
- D6/D7 are I2C (OLED) in stock firmware, not UART — document this
- Add Nebra pin remapping as a variant section

### Deploy updates to other Pis
- Sensor poller fix (once built) needs to go to all three Pis
- Home Pi and MRP still on old sensor poller code

---

## Session Notes

### Session 6 — 2026-03-28

**Firmware flash crash investigation and fix:**
- Firmware update attempt caused RepeaterWatch to crash mid-flash
- Root cause: `Requires=SerialMux.service` in the systemd service file — when the flash process stopped SerialMux, systemd killed RepeaterWatch too (hard dependency cascades both ways)
- Fixed on home Pi: changed to `Wants=SerialMux.service`, reloaded systemd, restarted service
- Fixed in repo: updated `systemd/meshcore-monitor.service` template and `docs/INSTALL.md` — both now use `Wants=` with a comment explaining why
- **`Wants=` is the correct permanent setting** — the firmware flash intentionally stops SerialMux, so `Requires=` must never be used

**adafruit-nrfutil installed on both Pis:**
- After the crash fix, the flash ran all the way to the flashing step — failed only because `adafruit-nrfutil` was missing
- Installed in the venv (`pip install adafruit-nrfutil`) and symlinked to `/usr/local/bin` on both Pis
- Added to `requirements.txt` with symlink note; added Step 5e to `docs/INSTALL.md`
- Confirmed DFU device enumerates correctly as `usb-Seeed_XIAO_nRF52840_Sense_...-if00` in bootloader mode — the code's wildcard fallback handles this correctly

**Both Pis synced and firmware-flash-ready:**
- meshcore-site2 already had `Wants=` set correctly — no service file change needed there
- Deployed updated code to meshcore-site2 via rsync; installed adafruit-nrfutil; restarted service
- Next step: retry a full firmware flash on the home Pi to confirm end-to-end success

**Disk space investigation and cleanup (home Pi — meshcore-site1):**
- Root filesystem was at 91% full (5.8 GB / 6.8 GB) on an 8 GB SD card
- Root cause: full desktop Raspberry Pi OS installed — Chromium (440 MB) and Firefox (250 MB) sitting unused on a headless server
- Also found: `/opt/mctomqtt/.nvm` (231 MB Node.js runtime, required), `/var/cache/apt` (137 MB, cleared), `/root/.cache/pip` (11 MB, cleared)
- Removed: Chromium, Firefox, rpd-wallpaper, pocketsphinx, plus orphaned packages via `apt autoremove`
- Result: 91% → 77% used, 607 MB → 1.5 GB free
- Note: 8 GB card is fundamentally small for this stack; larger card recommended before site deployment

**Upstream merge — 9 new commits from MrAlders0n/RepeaterWatch:**
- Clean merge, no conflicts (upstream didn't touch our added files)
- New features: noise floor rolling average on RF Signal graph, filters bogus 0 dBm AGC spikes, improved AS3935 lightning false-positive filtering, "delete old neighbours" button in Settings
- Admin page change: Tools and Settings tabs now require login; main dashboard stays public (no visible change while auth is disabled)
- Deployed to both Pis

**jjkroell/Repeater-Watch fork (VE7KOD) reviewed:**
- Has notable UX improvements: dark/light mode, mobile-responsive layout, better typography, sensor management modal
- Cannot be git-merged (no shared history with our tree); would need targeted manual implementation
- Noted for future consideration — hold until deployment is stable

### Session 5 — 2026-03-11

**USB relay wiring theory (documented in docs/gpio-wiring.md):**
- Confirmed from build photos: relay is wired NO/COM
- Working theory: relay interrupts VBUS (red wire) only on USB cable to Ikoka
- Normal operation: VBUS cut, Ikoka runs on external battery — USB serial (CDC) still works without VBUS
- Flashing: relay turns ON → VBUS connected → nRF52840 detects host power → enumerates as DFU device
- Relay stays ON for entire flash, turns OFF when done
- Note 2 in gpio-wiring.md updated with full theory and confirmation checklist
- **Status: UNCONFIRMED — awaiting official confirmation from MrAlders0n; test build planned**

**New deployment: meshcore-site2 (Compute Module 3, PI_IP)**
- Re-flashed to 64-bit Raspberry Pi OS (trixie) — matches home Pi architecture (aarch64)
- SSH access confirmed with existing `YOUR_SSH_KEY` key — same key will be used for all installs
- Full stack installed: SerialMux + RepeaterWatch (mctomqtt to be configured when radio arrives)
- New install note: `python3-dev` is required to build RPi.GPIO from source — not in INSTALL.md previously
- No radio connected: SerialMux configured with `/dev/ttyACM0` placeholder, keeps retrying
- RepeaterWatch service uses `Wants=SerialMux` (not `Requires=`) so it starts without virtual ports
- Dashboard live at http://PI_IP:5000 — serial errors in logs are expected, no radio connected

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
- Confirmed all GPIO pins are configurable via `.env`; I2C pins are fixed on Pi pins 3+5
- Confirmed BME280 (temp/humidity/pressure) and INA3221 (3-channel current/voltage) are both I2C — no GPIO pins needed
- INA3221 channels: ch0 = battery, ch1 = load, ch2 = solar; polled every 10s
- BME280 polled every 60s; uses I2C address 0x77 — note: some cheap modules default to 0x76
- Added Note 3 (BME280) and Note 4 (INA3221) to `docs/gpio-wiring.md`
- Added Note 5 (BQ24074) to `docs/gpio-wiring.md` — full explanation of all three GPIO pins (/CHG, /PGOOD, CE)
- Fixed error in doc: BQ24074 is GPIO only, not I2C (AS3935 is the one that needs I2C)
- Added "See note 5" references to all BQ24074 rows in the pin table
- Set up GitHub SSH key on new Mac (ed25519, `~/.ssh/YOUR_GITHUB_KEY`)

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
| 2026-03-11 | Use `Wants=` instead of `Requires=` for SerialMux in service file | Allows RepeaterWatch to start with no radio; also required permanently — firmware flash stops SerialMux intentionally, so `Requires=` would crash RepeaterWatch mid-flash |
| 2026-03-11 | Use same SSH key (`YOUR_SSH_KEY`) for all Pi installs | Simplifies access — one key works everywhere |
| 2026-03-11 | Recommend 64-bit OS for all Pi deployments | Matches home Pi exactly, avoids architecture differences in lgpio symlinks and pip builds |

---

## Open Questions

- Will the Pi have internet access at the mountain repeater site for initial setup?
- What network/IP scheme is used at the site — how will the dashboard be accessed remotely?
- USB relay circuit (GPIO 17): working theory documented (VBUS-only, NO/COM) — awaiting official confirmation from MrAlders0n; test build planned
- meshcore-site2: what will the permanent IP be once assigned?
- meshcore-site2: mctomqtt credentials and config — needed when radio is connected
- Home Pi SD card is 8 GB (77% used after cleanup) — consider upgrading to 32 GB before site deployment

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
- [x] `meshcore-monitor` systemd service installed, enabled, running (`Wants=SerialMux`)
- [x] Dashboard live at http://PI_IP:5000 — reading real device data
- [x] `adafruit-nrfutil` installed and symlinked to `/usr/local/bin`
- [x] Firmware flash pipeline tested — hardware sequence works end-to-end
- [ ] Wire GPIO 4 → Ikoka RESET pin and test remote reset from dashboard
- [ ] Retry full firmware flash (adafruit-nrfutil now installed — should complete)
- [ ] Write up full install process as `docs/INSTALL.md`

---

## Install Checklist (meshcore-site2 — CM3, PI_IP)

- [x] Pi running 64-bit Raspberry Pi OS / Debian 13 (trixie)
- [x] SSH enabled
- [x] `claude` user created with passwordless sudo
- [x] SerialMux installed at `/opt/SerialMux/`, systemd service running (placeholder port)
- [x] RepeaterWatch installed at `/opt/RepeaterWatch/`
- [x] `meshcoremon` system user created
- [x] Python venv created, dependencies installed, lgpio symlinked
- [x] `/etc/sudoers.d/meshcoremon` created
- [x] `.env` file configured (ttyV0, sensor poll off, auth disabled)
- [x] `RepeaterWatch` systemd service installed, enabled, running (`Wants=SerialMux` — permanent)
- [x] Dashboard live at http://PI_IP:5000
- [x] `adafruit-nrfutil` installed and symlinked to `/usr/local/bin`
- [x] Code synced to latest (2026-03-28 session)
- [ ] Connect radio (Ikoka stick)
- [ ] Update SerialMux `REAL_PORT` to actual by-id path
- [ ] Update `.env` `MESHCORE_FLASH_SERIAL_PORT` to actual by-id path
- [ ] Install and configure mctomqtt
- [ ] Wire GPIO 4 → Ikoka RESET pin
- [ ] Assign permanent IP, update records

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

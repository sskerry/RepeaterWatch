# RepeaterWatch — Project Progress

**Owner:** MYCALL (representing CLUB1 and CLUB2)
**Hardware target:** Raspberry Pi 4 + Ikoka stick MeshCore device
**Last updated:** 2026-03-07

---

## Goals & Status

| # | Goal | Status |
|---|------|--------|
| 0 | Git/GitHub setup | ✅ Done — private repo, SSH keys, remotes configured |
| 1 | Understand the codebase | ✅ Done — see notes below |
| 2 | Clean install documentation | 🔄 In progress |
| 3 | Get it running on repeater hardware | 🔄 In progress — home Pi set up as test bed |
| 4 | Explore sensors and GPIO | 🔄 In progress — GPIO wiring doc created, reset pin confirmed |
| 5 | Customize for CLUB1 / CLUB2 | ⬜ Not started |
| 6 | Maintain clean upstream upgrade path | ⬜ Ongoing consideration |

---

## Current Focus

**Goals 2 & 3 — Install documentation + home Pi test deployment**

Home Pi (meshcore-site1, PI_IP) is set up as a test bed. mctomqtt (letsmesh) is
already running on it. Next step is to install SerialMux and then RepeaterWatch alongside it.

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

---

## Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-07 | ~~Skip SerialMux~~ → **USE SerialMux** | mctomqtt (letsmesh) already runs on the Pi and holds the serial port; SerialMux lets both services share it |
| 2026-03-07 | Disable sensor polling initially | No sensor hardware on hand yet |
| 2026-03-07 | Use home Pi (meshcore-site1) as test bed | Low-stakes production deployment, safe to experiment on |
| 2026-03-07 | Store Claude SSH key in Nextcloud | Allows Claude Code access from any Mac without re-setup |

---

## Open Questions

- Will the Pi have internet access at the mountain repeater site for initial setup?
- What network/IP scheme is used at the site — how will the dashboard be accessed remotely?
- USB relay circuit (GPIO 17): what is it switching, is it necessary, and how is it wired? (ask MrAlders0n)
- What OS image will be used on the mountain Pi? (home Pi is Debian 13 trixie — use same?)

---

## Install Checklist (home Pi — meshcore-site1)

Already in place:
- [x] Pi running Debian 13 (trixie)
- [x] SSH enabled
- [x] mctomqtt (letsmesh) installed and running
- [x] Ikoka stick connected at `/dev/ttyACM0`
- [x] `claude` user created with passwordless sudo

Still to do:
- [ ] Install SerialMux
- [ ] Reconfigure mctomqtt to use SerialMux virtual port instead of raw serial
- [ ] Install RepeaterWatch to `/opt/RepeaterWatch`
- [ ] Set up Python venv and install dependencies
- [ ] Create `.env` file (use SerialMux virtual port, disable sensor polling)
- [ ] Test manually: `python app.py` — check logs, open dashboard in browser
- [ ] Install and enable RepeaterWatch systemd service
- [ ] Verify both mctomqtt and RepeaterWatch run together without serial conflict
- [ ] Wire GPIO 4 → Ikoka RESET pin and test remote reset from dashboard

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

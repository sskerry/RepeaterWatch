# RepeaterWatch — Project Progress

**Owner:** MYCALL (representing CLUB1 and CLUB2)
**Hardware target:** Raspberry Pi 4 + Ikoka stick MeshCore device
**Last updated:** 2026-03-07

---

## Goals & Status

| # | Goal | Status |
|---|------|--------|
| 1 | Understand the codebase | ✅ Done — see notes below |
| 2 | Clean install documentation | 🔄 In progress — draft in this file |
| 0 | Git/GitHub setup | ✅ Done — private repo, SSH keys, remotes configured |
| 3 | Get it running on repeater hardware | ⬜ Not started |
| 4 | Explore sensors and GPIO | ⬜ Not started (no extra hardware yet) |
| 5 | Customize for CLUB1 / CLUB2 | ⬜ Not started |
| 6 | Maintain clean upstream upgrade path | ⬜ Ongoing consideration |

---

## Current Focus

**Goal 2 — Installation documentation**

A full plain-English install guide was drafted in the first session (see session notes below). Next step is to validate it on the actual Pi hardware.

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
- Key decisions / findings:
  - Default serial port in config is `/dev/ttyV0` (SerialMux) — for direct Ikoka use, change to `/dev/ttyUSB0` or use `/dev/serial/by-id/...`
  - `MESHCORE_SENSOR_POLL=0` should be set until sensor hardware is available
  - No SerialMux needed for this deployment
  - Set `MESHCORE_SECRET_KEY` to a fixed value so login sessions survive app restarts
  - The `pi` user needs to be in the `dialout` group for serial port access

---

## Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-07 | Skip SerialMux | Only one program needs serial access |
| 2026-03-07 | Disable sensor polling initially | No sensor hardware on hand yet |

---

## Open Questions

- What serial port path does the Ikoka stick appear as on the Pi? (Check with `ls /dev/serial/by-id/` after plugging in)
- What OS image will be used on the Pi 4? (Raspberry Pi OS Lite recommended)
- Will the Pi have internet access at the repeater site for initial setup?
- What network/IP scheme is used at the site — how will the dashboard be accessed remotely?

---

## Install Checklist (for when we get to the Pi)

- [ ] Flash Pi OS to SD card
- [ ] Enable SSH, set hostname, configure WiFi or ethernet
- [ ] `sudo apt update && sudo apt upgrade -y`
- [ ] `sudo apt install python3 python3-pip python3-venv git -y`
- [ ] Copy project files to `/opt/RepeaterWatch`
- [ ] `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
- [ ] Plug in Ikoka stick, find its serial port (`ls /dev/serial/by-id/`)
- [ ] Create `.env` file with correct `MESHCORE_SERIAL_PORT` and other settings
- [ ] Add `pi` user to `dialout` group: `sudo usermod -aG dialout pi`
- [ ] Test manually: `python app.py` — check logs, open dashboard in browser
- [ ] Copy and enable systemd service: `sudo cp systemd/meshcore-monitor.service /etc/systemd/system/`
- [ ] `sudo systemctl daemon-reload && sudo systemctl enable --now meshcore-monitor`
- [ ] Verify service is running: `sudo systemctl status meshcore-monitor`

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

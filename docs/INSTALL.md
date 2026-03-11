# RepeaterWatch — Installation Guide
## Raspberry Pi 4 + Ikoka Stick (Seeed Studio XIAO nRF52840)

**Written for:** MYCALL / CLUB1 / CLUB2
**Validated on:** Debian GNU/Linux 13 (trixie), Python 3.13
**Last updated:** 2026-03-08

---

## Overview

This guide installs RepeaterWatch alongside the LetsMesh `mctomqtt` service on a Raspberry Pi 4.
Both services communicate with the same Ikoka MeshCore stick, so we use **SerialMux** to share
the serial port between them.

The three services run in this order:

```
Ikoka Stick (hardware)
    └── SerialMux         holds the real serial port, exposes virtual ports
            ├── mctomqtt  reads /dev/ttyV1 → publishes to LetsMesh cloud
            └── RepeaterWatch  reads /dev/ttyV0 → serves web dashboard on :5000
```

---

## Prerequisites

- Raspberry Pi 4 with Debian 13 (trixie) installed and SSH enabled
- Ikoka stick plugged in via USB **before booting**
- `mctomqtt` (LetsMesh service) already installed and running
- Internet access on the Pi (for apt and pip installs)
- The RepeaterWatch project files on your Mac (synced via Nextcloud or cloned from GitHub)

---

## Step 1 — Find the Ikoka stick's serial port

Plug in the Ikoka stick and run:

```bash
ls /dev/serial/by-id/
```

You should see a device with `Seeed_Studio_XIAO_nRF52840` in the name. Note the full path —
you will need it in Step 2. On our setup it looks like:

```
usb-Seeed_Studio_XIAO_nRF52840_85A0C3E1D8C354BB-if00
```

The full path is `/dev/serial/by-id/usb-Seeed_Studio_XIAO_nRF52840_85A0C3E1D8C354BB-if00`.
Your device ID (the hex string) will be different — use whatever yours shows.

The stick also appears as `/dev/ttyACM0` but use the full `/dev/serial/by-id/` path in configs
because it stays consistent even if USB devices are added or removed.

---

## Step 2 — Install SerialMux

SerialMux is a single Python script that holds the real serial port open and creates
three virtual ports that other programs can use simultaneously.

**Source:** https://github.com/MrAlders0n/SerialMux

### 2a. Create the directory and download the script

```bash
sudo mkdir -p /opt/SerialMux
cd /opt/SerialMux
sudo curl -o SerialMux.py https://raw.githubusercontent.com/MrAlders0n/SerialMux/main/SerialMux.py
```

### 2b. Edit the serial port in the script

Open the file and update the `REAL_PORT` line near the top:

```bash
sudo nano /opt/SerialMux/SerialMux.py
```

Change this line to match your device's full by-id path from Step 1:

```python
REAL_PORT = '/dev/serial/by-id/usb-Seeed_Studio_XIAO_nRF52840_YOUR_ID_HERE-if00'
```

Leave `BAUD = 115200` and `VPORTS` unchanged.

### 2c. Create a Python virtual environment and install pyserial

```bash
sudo python3 -m venv /opt/SerialMux/venv
sudo /opt/SerialMux/venv/bin/pip install pyserial
```

### 2d. Create the systemd service file

```bash
sudo nano /etc/systemd/system/SerialMux.service
```

Paste in:

```ini
[Unit]
Description=Serial Port Multiplexer
After=network.target

[Service]
Type=simple
ExecStart=/opt/SerialMux/venv/bin/python3 /opt/SerialMux/SerialMux.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 2e. Enable and start SerialMux

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now SerialMux
```

### 2f. Verify it's running and the virtual ports exist

```bash
sudo systemctl status SerialMux
ls -la /dev/ttyV*
```

You should see `/dev/ttyV0`, `/dev/ttyV1`, and `/dev/ttyV2` listed.

---

## Step 3 — Reconfigure mctomqtt to use SerialMux

Now that SerialMux is running, we need to point mctomqtt at the virtual port instead
of the real serial port. This is the only change to the mctomqtt configuration.

```bash
sudo nano /etc/mctomqtt/config.d/00-user.toml
```

Find the `[serial]` section and change the `ports` line to:

```toml
[serial]
ports = ["/dev/ttyV1"]
```

Then restart mctomqtt:

```bash
sudo systemctl restart mctomqtt
sudo systemctl status mctomqtt
```

It should start cleanly. mctomqtt now reads from `/dev/ttyV1` (a SerialMux virtual port)
instead of the real serial device.

---

## Step 4 — Create the meshcoremon service user

RepeaterWatch's firmware flashing feature needs a system user account to control services.

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin meshcoremon
```

Then create the sudoers rule that allows this user to stop and start services:

```bash
sudo visudo -f /etc/sudoers.d/meshcoremon
```

Paste in this single line exactly:

```
meshcoremon ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop SerialMux, /usr/bin/systemctl stop mctomqtt, /usr/bin/systemctl start SerialMux, /usr/bin/systemctl start mctomqtt
```

> **Note:** Even though RepeaterWatch runs as root (not as meshcoremon), this user and
> sudoers rule is referenced in the firmware flashing code and should be present.

---

## Step 5 — Install RepeaterWatch

### 5a. Create the directory and copy files

If deploying from your Mac via rsync:

```bash
sudo mkdir -p /opt/RepeaterWatch
```

Then from your Mac (replace IP with your Pi's address):

```bash
rsync -av --exclude='.git' --exclude='venv' --exclude='*.pyc' \
  --exclude='__pycache__' --exclude='*.db' --exclude='.env' \
  /path/to/RepeaterWatch/ user@PI_IP:/opt/RepeaterWatch/
```

### 5b. Install lgpio and Python dev headers

lgpio is needed for GPIO control. `python3-dev` is needed to compile RPi.GPIO from source:

```bash
sudo apt install -y python3-lgpio python3-dev
```

### 5c. Create a Python virtual environment and install dependencies

```bash
cd /opt/RepeaterWatch
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt
```

### 5d. Symlink lgpio into the virtual environment

This is required on Debian 13 / Python 3.13. The system lgpio package can't be installed
directly into a venv, so we create symlinks manually.

First, find your Python version in the venv:

```bash
ls /opt/RepeaterWatch/venv/lib/
# Example output: python3.13
```

Then create the symlinks (replace `python3.13` if your version differs):

```bash
SITE=/opt/RepeaterWatch/venv/lib/python3.13/site-packages

sudo ln -sf /usr/lib/python3/dist-packages/lgpio.py ${SITE}/lgpio.py

# Find and symlink the C extension (filename includes your architecture):
sudo ln -sf /usr/lib/python3/dist-packages/_lgpio.cpython-313-aarch64-linux-gnu.so \
  ${SITE}/_lgpio.cpython-313-aarch64-linux-gnu.so
```

Verify it works:

```bash
/opt/RepeaterWatch/venv/bin/python3 -c 'import lgpio; print("lgpio OK")'
```

---

## Step 6 — Create the .env configuration file

```bash
sudo nano /opt/RepeaterWatch/.env
```

Paste in the following, updating the values marked with `# ← CHANGE THIS`:

```bash
# Authentication — comment out to disable login, or set a password
#MESHCORE_PASSWORD=

# Secret key — generate with: python3 -c 'import secrets; print(secrets.token_hex(32))'
MESHCORE_SECRET_KEY=PASTE_GENERATED_KEY_HERE   # ← CHANGE THIS

# Serial port — RepeaterWatch uses SerialMux virtual port 0
MESHCORE_SERIAL_PORT=/dev/ttyV0
MESHCORE_SERIAL_BAUD=115200
MESHCORE_SERIAL_TIMEOUT=5

# Polling interval in seconds (300 = every 5 minutes)
MESHCORE_POLL_INTERVAL=300

# Database
MESHCORE_DB_PATH=/opt/RepeaterWatch/meshcore.db
MESHCORE_RETENTION_DAYS=30

# Web interface
MESHCORE_HOST=0.0.0.0
MESHCORE_PORT=5000
MESHCORE_DEBUG=0

# Firmware flash — use the real serial port by-id path (not SerialMux)
MESHCORE_FLASH_SERIAL_PORT=/dev/serial/by-id/usb-Seeed_Studio_XIAO_nRF52840_YOUR_ID_HERE-if00   # ← CHANGE THIS

MESHCORE_FIRMWARE_UPLOAD_DIR=/tmp/meshcore-fw

# Terminal — uses SerialMux virtual port 2
MESHCORE_TERMINAL_SERIAL_PORT=/dev/ttyV2
MESHCORE_TERMINAL_SERIAL_BAUD=115200

# Sensors — set to 1 only if sensor hardware is connected
MESHCORE_SENSOR_POLL=0

# GPIO pins (BCM numbering) — only needed if GPIO wiring is connected
MESHCORE_RADIO_RESET_GPIO=4
MESHCORE_USB_RELAY_GPIO=17
```

Generate a secret key:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Paste the output into the `MESHCORE_SECRET_KEY=` line.

Secure the file so only root can read it:

```bash
sudo chmod 600 /opt/RepeaterWatch/.env
```

---

## Step 7 — Create the systemd service file

The service **must** be named `RepeaterWatch` exactly — the dashboard code looks for this name
when displaying service status.

```bash
sudo nano /etc/systemd/system/RepeaterWatch.service
```

Paste in:

```ini
[Unit]
Description=RepeaterWatch
After=network.target SerialMux.service
Requires=SerialMux.service

[Service]
Type=simple
WorkingDirectory=/opt/RepeaterWatch
ExecStart=/opt/RepeaterWatch/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

> **Important:** The service runs as root (no `User=` line). This is required for:
> - The Pi web terminal feature (`/bin/login` needs root to authenticate users)
> - GPIO access (gpiochip requires root)
> - Service management via sudo

### Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now RepeaterWatch
```

---

## Step 8 — Verify everything is running

Check all three services:

```bash
sudo systemctl status SerialMux mctomqtt RepeaterWatch
```

All three should show `active (running)`.

Check the RepeaterWatch logs for a successful startup:

```bash
sudo journalctl -u RepeaterWatch -n 20 --no-pager
```

You should see lines like:

```
Connected to /dev/ttyV0 at 115200 baud
Device name: ...
Device firmware: ...
Running on http://0.0.0.0:5000
```

If you see `Connected to /dev/ttyV0` and device info, it is talking to the Ikoka stick.

Open a browser and go to `http://PI_IP_ADDRESS:5000` — the dashboard should load.

---

## Troubleshooting

### Dashboard doesn't load
- Check `sudo systemctl status RepeaterWatch` — is it running?
- Check `sudo journalctl -u RepeaterWatch -n 30 --no-pager` for errors

### "No data" or device not found
- Check SerialMux is running: `sudo systemctl status SerialMux`
- Verify virtual ports exist: `ls /dev/ttyV*`
- Verify Ikoka stick is plugged in: `ls /dev/serial/by-id/`
- Check the `REAL_PORT` in `/opt/SerialMux/SerialMux.py` matches your device

### mctomqtt fails after reconfiguring
- Confirm `/etc/mctomqtt/config.d/00-user.toml` has `ports = ["/dev/ttyV1"]`
- Check SerialMux is running first — mctomqtt will fail if ttyV1 doesn't exist yet
- Restart in order: `sudo systemctl restart SerialMux && sleep 2 && sudo systemctl restart mctomqtt`

### Pi terminal doesn't work in dashboard
- The service must run as root (no `User=` in the service file)
- Log in with a valid Pi user account (e.g., the account you use to SSH in)

### lgpio errors in logs (`can not open gpiochip`)
- The service must run as root (no `User=` in the service file)
- Re-check the service file and restart

### `stats-extpower: Unknown command` warning in logs
- This is harmless — the Ikoka custom firmware doesn't support this command
- It will appear on every poll cycle but does not affect operation

---

## Service Port Assignments

| Virtual Port | Used By | Purpose |
|---|---|---|
| `/dev/ttyV0` | RepeaterWatch | Main data polling |
| `/dev/ttyV1` | mctomqtt | LetsMesh cloud relay |
| `/dev/ttyV2` | RepeaterWatch | Web terminal feature |
| (real port) | SerialMux only | Physical Ikoka stick |

---

## Updating RepeaterWatch

When MrAlders0n releases updates to the original repo, here is how to pull them through
to your Pi deployments.

### On your Mac (pull upstream changes):

```bash
git fetch upstream
git merge upstream/main
git push origin main
```

`fetch` downloads the latest changes. `merge` applies them to your copy. `push` saves
them to your GitHub fork. If there are any conflicts Git will tell you — ask Claude Code
to help resolve them.

### On each Pi (deploy the update):

From your Mac, run the same rsync command used during install:

```bash
rsync -av --exclude='.git' --exclude='venv' --exclude='*.pyc' \
  --exclude='__pycache__' --exclude='*.db' --exclude='.env' \
  /path/to/RepeaterWatch/ user@PI_IP:/opt/RepeaterWatch/
```

Then restart the service:

```bash
ssh user@PI_IP "sudo systemctl restart RepeaterWatch"
```

The `.env` file and SQLite database are excluded from rsync and will not be affected.
The venv is also excluded — if `requirements.txt` changed in the update, re-run:

```bash
ssh user@PI_IP "sudo /opt/RepeaterWatch/venv/bin/pip install -r /opt/RepeaterWatch/requirements.txt"
```

---

## After Installation

- **GPIO reset wiring:** See `docs/gpio-wiring.md` for connecting the Pi GPIO 4 pin to the
  Ikoka stick's RESET pad. This enables the remote reset and firmware flash features.
- **Set a password:** To enable login protection, uncomment and set `MESHCORE_PASSWORD=` in `.env`
  then restart the service.
- **Customization:** Node name, branding, and club-specific fields can be changed without
  affecting the upstream upgrade path.

#!/usr/bin/env bash
# ============================================================================
# RepeaterWatch Full Stack Installer
# Installs: SerialMux → mctomqtt → RepeaterWatch
# ============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

header() { echo -e "\n${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"; echo -e "${BLUE}${BOLD}  $1${NC}"; echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}\n"; }
ok()     { echo -e "${GREEN}✓${NC}  $1"; }
warn()   { echo -e "${YELLOW}⚠${NC}  $1"; }
err()    { echo -e "${RED}✗${NC}  $1"; }
info()   { echo -e "${CYAN}ℹ${NC}  $1"; }

# Reattach stdin to terminal — required when run via curl | bash
exec < /dev/tty

if [[ $EUID -ne 0 ]]; then
    err "Please run as root: sudo bash install.sh"
    exit 1
fi

# ── Banner ───────────────────────────────────────────────────────────────────
clear
echo -e "${BOLD}"
echo "  ██████╗ ███████╗██████╗ ███████╗ █████╗ ████████╗███████╗██████╗ "
echo "  ██╔══██╗██╔════╝██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗"
echo "  ██████╔╝█████╗  ██████╔╝█████╗  ███████║   ██║   █████╗  ██████╔╝"
echo "  ██╔══██╗██╔══╝  ██╔═══╝ ██╔══╝  ██╔══██║   ██║   ██╔══╝  ██╔══██╗"
echo "  ██║  ██║███████╗██║     ███████╗██║  ██║   ██║   ███████╗██║  ██║"
echo "  ╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝"
echo -e "${NC}${CYAN}             W A T C H${NC}"
echo ""
echo -e "  Full stack installer: ${BOLD}SerialMux + mctomqtt + RepeaterWatch${NC}"
echo ""

# ── Gather inputs upfront ────────────────────────────────────────────────────
header "Configuration"
echo -e "  Before installing, we need a few details.\n"

# --- Connection mode ---
echo -e "  ${BOLD}Step 1/5 — Connection mode${NC}\n"
info "How is the Ikoka stick connected to this Pi?"
echo ""
echo -e "    ${BOLD}1${NC}) USB     — standard USB cable (default, most common)"
echo -e "    ${BOLD}2${NC}) Serial  — UART wiring to Pi GPIO pins 8/10 (RS232 firmware)"
echo ""
echo -en "${CYAN}?${NC}  Select [1]: "; read -r CONN_MODE_CHOICE </dev/tty
CONN_MODE_CHOICE="${CONN_MODE_CHOICE:-1}"

case "$CONN_MODE_CHOICE" in
    1) CONN_MODE="usb" ;;
    2) CONN_MODE="serial" ;;
    *) err "Invalid selection."; exit 1 ;;
esac
ok "Connection mode: $CONN_MODE"
echo ""

# --- Serial port (depends on connection mode) ---
if [[ "$CONN_MODE" == "usb" ]]; then
    echo -e "  ${BOLD}Step 2/5 — Physical serial port${NC}\n"

    mapfile -t USB_DEVICES < <(ls /dev/serial/by-id/ 2>/dev/null || true)

    if [[ ${#USB_DEVICES[@]} -eq 1 ]]; then
        SERIAL_PORT="/dev/serial/by-id/${USB_DEVICES[0]}"
        ok "Auto-detected: $SERIAL_PORT"
    elif [[ ${#USB_DEVICES[@]} -gt 1 ]]; then
        info "Multiple USB serial devices detected:"
        for i in "${!USB_DEVICES[@]}"; do
            echo -e "    ${BOLD}$((i+1))${NC}) /dev/serial/by-id/${USB_DEVICES[$i]}"
        done
        echo ""
        echo -en "${CYAN}?${NC}  Select device number [1]: "; read -r SEL </dev/tty
        SEL="${SEL:-1}"
        if [[ "$SEL" =~ ^[0-9]+$ ]] && (( SEL >= 1 && SEL <= ${#USB_DEVICES[@]} )); then
            SERIAL_PORT="/dev/serial/by-id/${USB_DEVICES[$((SEL-1))]}"
            ok "Selected: $SERIAL_PORT"
        else
            err "Invalid selection."
            exit 1
        fi
    else
        warn "No USB serial devices detected."
        info "Enter the path manually (e.g. /dev/ttyUSB0)."
        echo ""
        echo -en "${CYAN}?${NC}  Serial port: "; read -r SERIAL_PORT </dev/tty
        if [[ -z "$SERIAL_PORT" ]]; then
            err "Serial port is required."
            exit 1
        fi
        ok "Serial port: $SERIAL_PORT"
    fi
else
    echo -e "  ${BOLD}Step 2/5 — Serial UART port${NC}\n"
    SERIAL_PORT="/dev/ttyAMA0"
    ok "Using Pi hardware UART: $SERIAL_PORT"
    info "Make sure UART wiring is connected: Pi TX (Pin 8) → XIAO RX, Pi RX (Pin 10) → XIAO TX, GND"
fi
echo ""

# --- Hardware name ---
echo -e "  ${BOLD}Step 3/5 — Hardware name${NC}\n"
info "Name or description of this node's radio hardware."
info "Examples: Heltec T114, RAK 4631, Ikoka Stick 30dB"
echo ""
echo -en "${CYAN}?${NC}  Hardware name: "; read -r HARDWARE_NAME </dev/tty
if [[ -z "$HARDWARE_NAME" ]]; then HARDWARE_NAME="Unknown"; fi
ok "Hardware: $HARDWARE_NAME"
echo ""

# --- RepeaterWatch web port ---
echo -e "  ${BOLD}Step 4/5 — RepeaterWatch web port${NC}\n"
info "Port the dashboard will listen on (default: 5000)."
echo -en "${CYAN}?${NC}  Web port [5000]: "; read -r RW_PORT_RAW </dev/tty
RW_PORT="${RW_PORT_RAW:-5000}"
ok "Web port: $RW_PORT"
echo ""

# --- RepeaterWatch git repo ---
echo -e "  ${BOLD}Step 5/5 — RepeaterWatch Git repository${NC}\n"
info "Which RepeaterWatch repo to clone?"
echo ""
echo -e "    ${BOLD}1${NC}) MrAlders0n/RepeaterWatch  (upstream original)"
echo -e "    ${BOLD}2${NC}) sskerry/RepeaterWatch     (security + UX improvements)"
echo -e "    ${BOLD}3${NC}) jjkroell/Repeater-Watch   (Jesse's UX fork)"
echo -e "    ${BOLD}4${NC}) Custom URL"
echo ""
echo -en "${CYAN}?${NC}  Select [1]: "; read -r RW_REPO_CHOICE </dev/tty
RW_REPO_CHOICE="${RW_REPO_CHOICE:-1}"

case "$RW_REPO_CHOICE" in
    1) RW_REPO="https://github.com/MrAlders0n/RepeaterWatch.git" ;;
    2) RW_REPO="https://github.com/sskerry/RepeaterWatch.git" ;;
    3) RW_REPO="https://github.com/jjkroell/Repeater-Watch.git" ;;
    4)
        echo -en "${CYAN}?${NC}  Repo URL: "; read -r RW_REPO </dev/tty
        if [[ -z "$RW_REPO" ]]; then err "Repo URL required."; exit 1; fi
        ;;
    *) err "Invalid selection."; exit 1 ;;
esac
ok "Repo: $RW_REPO"
echo ""

echo -e "  ${BOLD}Login password will be set interactively during the install.${NC}"
echo -e "  ${BOLD}mctomqtt will ask for your IATA code and LetsMesh credentials.${NC}\n"
echo -e "${YELLOW}  Starting installation in 3 seconds...${NC}"
sleep 3

# ── Step 1: System dependencies ──────────────────────────────────────────────
header "Step 1/4 — System Dependencies"

info "Updating package lists..."
apt-get update -qq
ok "Package lists updated."

info "Installing system packages..."
apt-get install -y -qq \
    git \
    python3 python3-venv python3-pip python3-dev \
    python3-lgpio python3-serial \
    curl \
    i2c-tools \
    || { err "Failed to install system packages."; exit 1; }
ok "System packages installed."

# Enable I2C interface if not already enabled (needed for sensors)
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null \
   && ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
    # Try the new firmware path first (Bookworm+), fall back to legacy
    BOOT_CONFIG="/boot/firmware/config.txt"
    [[ ! -f "$BOOT_CONFIG" ]] && BOOT_CONFIG="/boot/config.txt"
    if [[ -f "$BOOT_CONFIG" ]]; then
        echo "dtparam=i2c_arm=on" >> "$BOOT_CONFIG"
        ok "I2C enabled in $BOOT_CONFIG (takes effect after reboot)."
    fi
fi

# ── Step 1b: UART kernel config (serial mode only) ──────────────────────────
if [[ "$CONN_MODE" == "serial" ]]; then
    header "Step 1b — UART Kernel Configuration"

    NEEDS_REBOOT=0

    # Ensure UART is enabled in boot config
    BOOT_CONFIG="/boot/firmware/config.txt"
    [[ ! -f "$BOOT_CONFIG" ]] && BOOT_CONFIG="/boot/config.txt"

    if ! grep -q "^enable_uart=1" "$BOOT_CONFIG" 2>/dev/null; then
        echo "enable_uart=1" >> "$BOOT_CONFIG"
        ok "UART enabled in $BOOT_CONFIG"
        NEEDS_REBOOT=1
    else
        ok "UART already enabled in $BOOT_CONFIG"
    fi

    # Remove kernel serial console so Linux doesn't claim /dev/ttyAMA0
    CMDLINE="/boot/firmware/cmdline.txt"
    [[ ! -f "$CMDLINE" ]] && CMDLINE="/boot/cmdline.txt"

    if grep -q "console=serial0" "$CMDLINE" 2>/dev/null; then
        cp "$CMDLINE" "${CMDLINE}.bak"
        sed -i 's/console=serial0,[0-9]* //' "$CMDLINE"
        ok "Kernel serial console removed from $CMDLINE (backup: ${CMDLINE}.bak)"
        NEEDS_REBOOT=1
    else
        ok "Kernel serial console already disabled."
    fi

    # Disable serial-getty on ttyAMA0 if active (login prompt would steal the port)
    if systemctl is-enabled serial-getty@ttyAMA0.service &>/dev/null; then
        systemctl stop serial-getty@ttyAMA0.service 2>/dev/null || true
        systemctl disable serial-getty@ttyAMA0.service 2>/dev/null || true
        ok "Disabled serial-getty on ttyAMA0 (was claiming the UART for login)."
    else
        ok "serial-getty on ttyAMA0 already disabled."
    fi

    # On Pi 3/4/Zero W, Bluetooth uses ttyAMA0 by default — move BT to mini-UART
    # so we can use ttyAMA0 for MeshCore. This adds a dtoverlay if not already present.
    if ! grep -q "^dtoverlay=miniuart-bt" "$BOOT_CONFIG" 2>/dev/null \
       && ! grep -q "^dtoverlay=disable-bt" "$BOOT_CONFIG" 2>/dev/null; then
        info "Bluetooth may be using /dev/ttyAMA0 — freeing it for MeshCore."
        echo ""
        echo -e "    ${BOLD}1${NC}) Move Bluetooth to mini-UART (recommended — BT still works)"
        echo -e "    ${BOLD}2${NC}) Disable Bluetooth entirely"
        echo -e "    ${BOLD}3${NC}) Skip (only if you know BT is not using ttyAMA0)"
        echo ""
        echo -en "${CYAN}?${NC}  Select [1]: "; read -r BT_CHOICE </dev/tty
        BT_CHOICE="${BT_CHOICE:-1}"
        case "$BT_CHOICE" in
            1)
                echo "dtoverlay=miniuart-bt" >> "$BOOT_CONFIG"
                ok "Bluetooth moved to mini-UART (ttyAMA0 freed for MeshCore)."
                NEEDS_REBOOT=1
                ;;
            2)
                echo "dtoverlay=disable-bt" >> "$BOOT_CONFIG"
                systemctl disable hciuart.service 2>/dev/null || true
                ok "Bluetooth disabled. ttyAMA0 freed for MeshCore."
                NEEDS_REBOOT=1
                ;;
            3)
                warn "Skipped — if UART doesn't work, Bluetooth may be the cause."
                ;;
            *)
                warn "Invalid choice — skipping."
                ;;
        esac
    else
        ok "Bluetooth already configured to not use ttyAMA0."
    fi

    if [[ "$NEEDS_REBOOT" == "1" ]]; then
        warn "A reboot will be needed after installation for UART changes to take effect."
    fi
    echo ""
fi

# ── Step 2: SerialMux ────────────────────────────────────────────────────────
header "Step 2/4 — SerialMux"

SERIALMUX_DIR="/opt/SerialMux"

if [[ -d "$SERIALMUX_DIR" ]]; then
    warn "SerialMux already found at $SERIALMUX_DIR — skipping clone."
else
    info "Cloning SerialMux..."
    git clone -q https://github.com/MrAlders0n/SerialMux.git "$SERIALMUX_DIR"
    ok "Cloned to $SERIALMUX_DIR"
fi

info "Configuring serial port: $SERIAL_PORT"
sed -i "s|REAL_PORT = '.*'|REAL_PORT = '$SERIAL_PORT'|" "$SERIALMUX_DIR/SerialMux.py"
ok "REAL_PORT configured."

cat > /etc/systemd/system/SerialMux.service <<EOF
[Unit]
Description=SerialMux - Python Serial Port Multiplexer
After=local-fs.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $SERIALMUX_DIR/SerialMux.py
Restart=on-failure
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now SerialMux
ok "SerialMux service enabled and started."

info "Waiting for virtual ports (/dev/ttyV0, /dev/ttyV1, /dev/ttyV2)..."
for i in $(seq 15); do [[ -e /dev/ttyV1 ]] && break; sleep 1; done
if [[ -e /dev/ttyV1 ]]; then
    ok "Virtual ports ready."
else
    warn "Virtual ports not yet visible — SerialMux may still be starting."
fi

# ── Step 3: mctomqtt ─────────────────────────────────────────────────────────
header "Step 3/4 — mctomqtt"
info "The mctomqtt installer will now run and ask for your IATA code and LetsMesh credentials."
echo ""

if [[ -d /opt/mctomqtt ]]; then
    warn "mctomqtt already found at /opt/mctomqtt — skipping installer."
else
    bash <(curl -fsSL https://raw.githubusercontent.com/Cisien/meshcoretomqtt/main/install.sh)
    echo ""
    ok "mctomqtt installed."
fi

# Override: make mctomqtt wait for SerialMux virtual port before starting
mkdir -p /etc/systemd/system/mctomqtt.service.d
cat > /etc/systemd/system/mctomqtt.service.d/override.conf <<EOF
[Service]
ExecStartPre=
ExecStartPre=/bin/bash -c 'for i in \$(seq 30); do [ -e /dev/ttyV1 ] && exit 0; sleep 1; done; exit 1'
Restart=on-failure
RestartSec=15
RestartForceExitStatus=0
EOF

# Update serial port in mctomqtt config to use SerialMux virtual port
if [[ -f /etc/mctomqtt/config.d/00-user.toml ]]; then
    sed -i 's|ports = \[.*\]|ports = ["/dev/ttyV1"]|' /etc/mctomqtt/config.d/00-user.toml
    ok "mctomqtt serial port set to /dev/ttyV1 (SerialMux virtual port)."
fi

systemctl daemon-reload
systemctl restart mctomqtt
ok "mctomqtt restarted."

# ── Step 4: RepeaterWatch ────────────────────────────────────────────────────
header "Step 4/4 — RepeaterWatch"

RW_DIR="/opt/RepeaterWatch"

# RepeaterWatch runs as root — required for:
#   - /bin/login (Pi terminal via WebSocket)
#   - GPIO access (radio reset, USB relay, sensors)
#   - systemd service management (restart services, reboot Pi)

if [[ -d "$RW_DIR/.git" ]]; then
    warn "RepeaterWatch already installed at $RW_DIR — skipping clone."
else
    info "Cloning RepeaterWatch..."
    git clone -q "$RW_REPO" "$RW_DIR"
    ok "Cloned to $RW_DIR"
fi

if [[ ! -d "$RW_DIR/venv" ]]; then
    info "Creating Python virtual environment..."
    python3 -m venv "$RW_DIR/venv"
    ok "venv created."
fi

info "Installing Python dependencies..."
"$RW_DIR/venv/bin/pip" install -q -r "$RW_DIR/requirements.txt"
ok "Python dependencies installed."

# Symlink adafruit-nrfutil into PATH for firmware flashing
if [[ -f "$RW_DIR/venv/bin/adafruit-nrfutil" ]] && [[ ! -f /usr/local/bin/adafruit-nrfutil ]]; then
    ln -sf "$RW_DIR/venv/bin/adafruit-nrfutil" /usr/local/bin/adafruit-nrfutil
    ok "adafruit-nrfutil symlinked to /usr/local/bin."
elif [[ -f /usr/local/bin/adafruit-nrfutil ]]; then
    ok "adafruit-nrfutil already in PATH."
fi

# Symlink lgpio from system packages into venv
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
LGPIO_PY=$(find /usr/lib/python3 -name "lgpio.py" ! -path "*/gpiozero/*" 2>/dev/null | head -1 || true)
SITE_SYS=$(dirname "$LGPIO_PY" 2>/dev/null || true)
SITE_VENV="$RW_DIR/venv/lib/python${PYVER}/site-packages"

if [[ -n "$LGPIO_PY" ]] && [[ ! -f "$SITE_VENV/lgpio.py" ]]; then
    ln -sf "$SITE_SYS/lgpio.py" "$SITE_VENV/lgpio.py"
    LGPIO_SO=$(ls "$SITE_SYS"/_lgpio*.so 2>/dev/null | head -1 || true)
    [[ -n "$LGPIO_SO" ]] && ln -sf "$LGPIO_SO" "$SITE_VENV/$(basename "$LGPIO_SO")"
    ok "lgpio symlinked into venv."
elif [[ -f "$SITE_VENV/lgpio.py" ]]; then
    ok "lgpio already symlinked."
else
    warn "lgpio not found in system packages. Run: sudo apt install python3-lgpio"
fi

if [[ ! -f "$RW_DIR/.env" ]]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > "$RW_DIR/.env" <<EOF
# Authentication — set password via setup_auth.py or the Settings page
# MESHCORE_PASSWORD_HASH=
MESHCORE_SECRET_KEY=$SECRET_KEY

# Connection mode: "usb" or "serial"
# usb    = Ikoka connected via USB cable (standard firmware, /dev/ttyACM0)
# serial = Ikoka connected via Pi UART pins 8/10 (RS232 firmware, /dev/ttyAMA0)
MESHCORE_CONNECTION_MODE=$CONN_MODE

# Serial (via SerialMux virtual port)
MESHCORE_SERIAL_PORT=/dev/ttyV0
MESHCORE_SERIAL_BAUD=115200
MESHCORE_SERIAL_TIMEOUT=5

# Polling
MESHCORE_POLL_INTERVAL=300

# Database
MESHCORE_DB_PATH=$RW_DIR/meshcore.db
MESHCORE_RETENTION_DAYS=30

# Flask
MESHCORE_HOST=0.0.0.0
MESHCORE_PORT=$RW_PORT
MESHCORE_DEBUG=0

# Firmware flash — use the real serial port (not SerialMux)
# For USB mode: /dev/serial/by-id/usb-Seeed_Studio_XIAO_nRF52840_...-if00
# For serial mode: firmware flashing still uses USB if the cable is connected
MESHCORE_FLASH_SERIAL_PORT=$SERIAL_PORT
MESHCORE_FIRMWARE_UPLOAD_DIR=/tmp/meshcore-fw

# Terminal
MESHCORE_TERMINAL_SERIAL_PORT=/dev/ttyV2
MESHCORE_TERMINAL_SERIAL_BAUD=115200

# Hardware label (shown on dashboard — board type is also auto-detected from serial)
MESHCORE_HARDWARE=$HARDWARE_NAME

# Login protection (fail2ban-style)
# MESHCORE_LOGIN_MAX_ATTEMPTS=5
# MESHCORE_LOGIN_LOCKOUT_SECS=300

# Trusted reverse proxies (comma-separated IPs, e.g. "127.0.0.1,10.0.0.1")
# MESHCORE_TRUSTED_PROXIES=

# Sensors (all disabled by default — enable in the Sensors tab)
MESHCORE_SENSOR_POLL=0
# MESHCORE_SENSOR_INA3221=0
# MESHCORE_SENSOR_BME280=0
# MESHCORE_SENSOR_LIS2DW12=0
# MESHCORE_SENSOR_AS3935=0
# MESHCORE_SENSOR_BQ24074=0
EOF
    chmod 640 "$RW_DIR/.env"
    ok ".env written."
else
    warn ".env already exists — skipping (not overwritten)."
fi

echo ""
echo -e "  ${BOLD}Optional: Set a login password${NC}\n"
echo -e "  Without a password, the dashboard is fully open (all features accessible)."
echo -e "  Set a password if this install will be accessible from the internet.\n"
echo -en "${CYAN}?${NC}  Set a password now? [y/N]: "; read -r SET_PW </dev/tty
if [[ "$SET_PW" =~ ^[Yy] ]]; then
    "$RW_DIR/venv/bin/python3" "$RW_DIR/setup_auth.py" || true
else
    info "No password set — dashboard is fully open. Set one later via Settings or setup_auth.py."
fi
echo ""

# Install systemd service — runs as root (no User= line)
cp "$RW_DIR/systemd/meshcore-monitor.service" /etc/systemd/system/RepeaterWatch.service
systemctl daemon-reload
systemctl enable --now RepeaterWatch
ok "RepeaterWatch service enabled and started."

# ── Final status ─────────────────────────────────────────────────────────────
header "Installation Complete"

echo -e "  Service status:\n"
for svc in SerialMux mctomqtt RepeaterWatch; do
    if systemctl is-active --quiet "$svc"; then
        ok "$svc is running"
    else
        warn "$svc is NOT running — check: sudo journalctl -u $svc -n 20"
    fi
done

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo -e "  ${BOLD}Dashboard:${NC}  ${GREEN}http://${IP}:${RW_PORT}${NC}"
echo ""
echo -e "  ${BOLD}Useful commands:${NC}"
echo -e "    sudo systemctl status RepeaterWatch"
echo -e "    sudo journalctl -u RepeaterWatch -f"
echo -e "    sudo journalctl -u mctomqtt -f"
echo -e "    sudo journalctl -u SerialMux -f"
echo ""
echo -e "  ${BOLD}Change password:${NC}"
echo -e "    sudo $RW_DIR/venv/bin/python3 $RW_DIR/setup_auth.py"
echo -e "    sudo systemctl restart RepeaterWatch"
echo ""

# Reboot prompt for serial mode (UART won't work until kernel releases the port)
if [[ "$CONN_MODE" == "serial" ]] && [[ "${NEEDS_REBOOT:-0}" == "1" ]]; then
    echo ""
    warn "IMPORTANT: A reboot is required for UART serial mode to work."
    info "The kernel serial console was disabled, but this only takes effect after reboot."
    info "Services will start automatically after reboot."
    echo ""
    echo -en "${CYAN}?${NC}  Reboot now? [Y/n]: "; read -r DO_REBOOT </dev/tty
    DO_REBOOT="${DO_REBOOT:-Y}"
    if [[ "$DO_REBOOT" =~ ^[Yy] ]]; then
        ok "Rebooting..."
        reboot
    else
        warn "Remember to reboot before the serial connection will work."
    fi
fi

ok "All done!"

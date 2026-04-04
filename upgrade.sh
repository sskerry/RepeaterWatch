#!/usr/bin/env bash
# ============================================================================
# RepeaterWatch Upgrade Script
# Upgrades an existing RepeaterWatch installation from any fork:
#   - MrAlders0n/RepeaterWatch (upstream original)
#   - sskerry/RepeaterWatch (security + UX improvements)
#   - jjkroell/Repeater-Watch (Jesse's UX fork)
#   - any other fork
#
# Preserves: .env, meshcore.db, venv (updated), systemd service
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
    err "Please run as root: sudo bash upgrade.sh"
    exit 1
fi

RW_DIR="/opt/RepeaterWatch"

# ── Pre-flight checks ───────────────────────────────────────────────────────
clear
header "RepeaterWatch Upgrade"

if [[ ! -d "$RW_DIR" ]]; then
    err "RepeaterWatch not found at $RW_DIR"
    info "Run install.sh for a fresh installation instead."
    exit 1
fi

# Detect current installation
CURRENT_REMOTE=""
CURRENT_BRANCH=""
if [[ -d "$RW_DIR/.git" ]]; then
    CURRENT_REMOTE=$(git -C "$RW_DIR" remote get-url origin 2>/dev/null || echo "unknown")
    CURRENT_BRANCH=$(git -C "$RW_DIR" branch --show-current 2>/dev/null || echo "unknown")
    info "Current repo:   $CURRENT_REMOTE"
    info "Current branch: $CURRENT_BRANCH"
else
    warn "No .git directory found — installed via rsync or manual copy."
    CURRENT_REMOTE="(none — manual install)"
fi
echo ""

# ── Choose upgrade source ───────────────────────────────────────────────────
info "Which repo do you want to upgrade to?"
echo ""
echo -e "    ${BOLD}1${NC}) MrAlders0n/RepeaterWatch  (upstream original)"
echo -e "    ${BOLD}2${NC}) sskerry/RepeaterWatch     (security + UX improvements)"
echo -e "    ${BOLD}3${NC}) jjkroell/Repeater-Watch   (Jesse's UX fork)"
echo -e "    ${BOLD}4${NC}) Custom URL"
echo ""
echo -en "${CYAN}?${NC}  Select [1]: "; read -r REPO_CHOICE </dev/tty
REPO_CHOICE="${REPO_CHOICE:-1}"

case "$REPO_CHOICE" in
    1) NEW_REPO="https://github.com/MrAlders0n/RepeaterWatch.git"; NEW_BRANCH="main" ;;
    2) NEW_REPO="https://github.com/sskerry/RepeaterWatch.git"; NEW_BRANCH="main" ;;
    3) NEW_REPO="https://github.com/jjkroell/Repeater-Watch.git"; NEW_BRANCH="main" ;;
    4)
        echo -en "${CYAN}?${NC}  Repo URL: "; read -r NEW_REPO </dev/tty
        if [[ -z "$NEW_REPO" ]]; then err "Repo URL required."; exit 1; fi
        echo -en "${CYAN}?${NC}  Branch [main]: "; read -r NEW_BRANCH_RAW </dev/tty
        NEW_BRANCH="${NEW_BRANCH_RAW:-main}"
        ;;
    *) err "Invalid selection."; exit 1 ;;
esac

ok "Upgrading to: $NEW_REPO (branch: $NEW_BRANCH)"
echo ""

# ── Confirmation ─────────────────────────────────────────────────────────────
echo -e "  ${BOLD}What this upgrade will do:${NC}"
echo -e "    - Back up your database"
echo -e "    - Replace all code files with the new version"
echo -e "    - Preserve your .env configuration"
echo -e "    - Update Python dependencies"
echo -e "    - Restart the RepeaterWatch service"
echo ""
echo -e "  ${BOLD}What it will NOT touch:${NC}"
echo -e "    - Your .env file (passwords, serial port, settings)"
echo -e "    - Your database (meshcore.db)"
echo -e "    - SerialMux and mctomqtt"
echo ""
echo -en "${CYAN}?${NC}  Continue? [y/N]: "; read -r CONFIRM </dev/tty
if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
    info "Upgrade cancelled."
    exit 0
fi
echo ""

# ── Step 1: Back up ──────────────────────────────────────────────────────────
header "Step 1/5 — Backup"

BACKUP_DIR="/tmp/repeaterwatch-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Back up database
if [[ -f "$RW_DIR/meshcore.db" ]]; then
    cp "$RW_DIR/meshcore.db" "$BACKUP_DIR/meshcore.db"
    ok "Database backed up to $BACKUP_DIR/meshcore.db"
else
    info "No database found — skipping database backup."
fi

# Back up .env
if [[ -f "$RW_DIR/.env" ]]; then
    cp "$RW_DIR/.env" "$BACKUP_DIR/.env"
    ok ".env backed up to $BACKUP_DIR/.env"
else
    warn "No .env file found."
fi

# Back up the venv marker so we know if it existed
[[ -d "$RW_DIR/venv" ]] && touch "$BACKUP_DIR/.had-venv"

# ── Step 2: Install system dependencies ──────────────────────────────────────
header "Step 2/5 — System Dependencies"

apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip python3-dev python3-lgpio python3-serial curl
ok "System packages up to date."

# ── Step 3: Replace code ─────────────────────────────────────────────────────
header "Step 3/5 — Update Code"

# Clone new version to a temp directory, then swap
TEMP_DIR=$(mktemp -d)
info "Cloning $NEW_REPO ($NEW_BRANCH)..."
git clone -q --branch "$NEW_BRANCH" "$NEW_REPO" "$TEMP_DIR"
ok "Cloned to temp directory."

# Stop service before swapping files
if systemctl is-active --quiet RepeaterWatch 2>/dev/null; then
    systemctl stop RepeaterWatch
    ok "RepeaterWatch service stopped."
fi

# Remove old code files but preserve .env, database, and venv
info "Replacing code files..."
# Save protected files
[[ -f "$RW_DIR/.env" ]] && cp "$RW_DIR/.env" /tmp/.rw-env-save
[[ -f "$RW_DIR/meshcore.db" ]] && cp "$RW_DIR/meshcore.db" /tmp/.rw-db-save

# Remove old code (keep venv)
find "$RW_DIR" -mindepth 1 -maxdepth 1 \
    ! -name 'venv' \
    ! -name '.env' \
    ! -name 'meshcore.db' \
    -exec rm -rf {} +

# Copy new code in
cp -r "$TEMP_DIR"/. "$RW_DIR"/
rm -rf "$TEMP_DIR"

# Restore protected files (in case they got overwritten)
[[ -f /tmp/.rw-env-save ]] && cp /tmp/.rw-env-save "$RW_DIR/.env" && rm /tmp/.rw-env-save
[[ -f /tmp/.rw-db-save ]] && cp /tmp/.rw-db-save "$RW_DIR/meshcore.db" && rm /tmp/.rw-db-save

ok "Code updated."

# ── Step 4: Update dependencies ──────────────────────────────────────────────
header "Step 4/5 — Python Dependencies"

if [[ ! -d "$RW_DIR/venv" ]]; then
    info "Creating Python virtual environment..."
    python3 -m venv "$RW_DIR/venv"
    ok "venv created."
fi

info "Installing/updating Python dependencies..."
"$RW_DIR/venv/bin/pip" install -q -r "$RW_DIR/requirements.txt"
ok "Python dependencies installed."

# Symlink adafruit-nrfutil into PATH for firmware flashing
if [[ -f "$RW_DIR/venv/bin/adafruit-nrfutil" ]] && [[ ! -f /usr/local/bin/adafruit-nrfutil ]]; then
    ln -sf "$RW_DIR/venv/bin/adafruit-nrfutil" /usr/local/bin/adafruit-nrfutil
    ok "adafruit-nrfutil symlinked to /usr/local/bin."
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
fi

# ── Step 5: Check .env for new settings ──────────────────────────────────────
header "Step 5/5 — Configuration Check"

# Ensure critical settings exist in .env (add if missing, don't overwrite existing)
ENV_FILE="$RW_DIR/.env"
ADDED_SETTINGS=0

add_if_missing() {
    local key="$1"
    local default="$2"
    local comment="${3:-}"
    if ! grep -q "^${key}=" "$ENV_FILE" && ! grep -q "^# *${key}=" "$ENV_FILE"; then
        [[ -n "$comment" ]] && echo -e "\n# $comment" >> "$ENV_FILE"
        echo "${key}=${default}" >> "$ENV_FILE"
        info "Added new setting: ${key}=${default}"
        ADDED_SETTINGS=1
    fi
}

add_if_missing "MESHCORE_SECRET_KEY" "$(python3 -c 'import secrets; print(secrets.token_hex(32))')" "Secret key for session cookies"
add_if_missing "MESHCORE_TERMINAL_SERIAL_PORT" "/dev/ttyV2" "Terminal (serial console via WebSocket)"
add_if_missing "MESHCORE_TERMINAL_SERIAL_BAUD" "115200"
add_if_missing "MESHCORE_FIRMWARE_UPLOAD_DIR" "/tmp/meshcore-fw" "Firmware flash"

if [[ $ADDED_SETTINGS -eq 0 ]]; then
    ok ".env is up to date — no new settings needed."
else
    ok "New settings added to .env."
fi

# Update systemd service file
cp "$RW_DIR/systemd/meshcore-monitor.service" /etc/systemd/system/RepeaterWatch.service
systemctl daemon-reload
ok "Systemd service file updated."

# ── Migration: meshcoremon → root ────────────────────────────────────────────
# Older installs (from jjkroell's fork) ran as 'meshcoremon' user.
# RepeaterWatch must run as root for GPIO, terminal, and service management.
# Fix ownership if files are still owned by meshcoremon.
if id meshcoremon &>/dev/null; then
    warn "Found 'meshcoremon' user from older install."
    info "RepeaterWatch now runs as root — fixing file ownership..."
    chown -R root:root "$RW_DIR"
    chmod 640 "$RW_DIR/.env"
    ok "File ownership updated to root."
    info "The 'meshcoremon' user is no longer needed."
    info "Remove it manually if desired: sudo userdel meshcoremon"
fi

# Clean up old sudoers file if it exists (not needed when running as root)
if [[ -f /etc/sudoers.d/meshcoremon ]]; then
    rm -f /etc/sudoers.d/meshcoremon
    ok "Removed old meshcoremon sudoers file (not needed — service runs as root)."
fi

# ── Start service ────────────────────────────────────────────────────────────
systemctl start RepeaterWatch
ok "RepeaterWatch service started."

# ── Summary ──────────────────────────────────────────────────────────────────
header "Upgrade Complete"

echo -e "  ${BOLD}From:${NC} $CURRENT_REMOTE"
echo -e "  ${BOLD}To:${NC}   $NEW_REPO ($NEW_BRANCH)"
echo ""

if systemctl is-active --quiet RepeaterWatch 2>/dev/null; then
    ok "RepeaterWatch is running."
else
    warn "RepeaterWatch is NOT running — check: sudo journalctl -u RepeaterWatch -n 20"
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
PORT=$(grep -oP 'MESHCORE_PORT=\K\d+' "$RW_DIR/.env" 2>/dev/null || echo "5000")
echo ""
echo -e "  ${BOLD}Dashboard:${NC}  ${GREEN}http://${IP}:${PORT}${NC}"
echo ""
echo -e "  ${BOLD}Backup location:${NC} $BACKUP_DIR"
echo -e "    Restore database: cp $BACKUP_DIR/meshcore.db $RW_DIR/meshcore.db"
echo -e "    Restore config:   cp $BACKUP_DIR/.env $RW_DIR/.env"
echo ""
ok "All done!"

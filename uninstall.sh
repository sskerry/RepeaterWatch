#!/usr/bin/env bash
# ============================================================================
# RepeaterWatch Full Stack Uninstaller
# Removes: RepeaterWatch, mctomqtt, SerialMux
# ============================================================================
set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

header() { echo -e "\n${BLUE}${BOLD}══════════════════════════════════════════════════${NC}"; echo -e "${BLUE}${BOLD}  $1${NC}"; echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════${NC}\n"; }
ok()     { echo -e "${GREEN}✓${NC}  $1"; }
warn()   { echo -e "${YELLOW}⚠${NC}  $1"; }
info()   { echo -e "${CYAN}ℹ${NC}  $1"; }

yn() {
    local default="${2:-n}"
    local prompt="$1"
    [[ "$default" == "y" ]] && prompt+=" [Y/n]: " || prompt+=" [y/N]: "
    read -rp "$(echo -e "${CYAN}?${NC}  $prompt")" resp </dev/tty
    resp="${resp:-$default}"
    [[ "$resp" =~ ^[Yy] ]]
}

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}✗${NC}  Please run as root: sudo bash uninstall.sh"
    exit 1
fi

clear
header "RepeaterWatch Uninstaller"

echo -e "  This will remove ${BOLD}RepeaterWatch, mctomqtt, and SerialMux${NC} from this system.\n"

if ! yn "Are you sure you want to continue?" n; then
    info "Uninstallation cancelled."
    exit 0
fi

# ── RepeaterWatch ─────────────────────────────────────────────────────────────
header "Removing RepeaterWatch"

if systemctl is-active --quiet RepeaterWatch 2>/dev/null; then
    systemctl stop RepeaterWatch
    ok "Service stopped."
fi
if systemctl is-enabled --quiet RepeaterWatch 2>/dev/null; then
    systemctl disable RepeaterWatch
    ok "Service disabled."
fi
rm -f /etc/systemd/system/RepeaterWatch.service
systemctl reset-failed RepeaterWatch 2>/dev/null || true
ok "Service file removed."

rm -f /etc/sudoers.d/meshcoremon
ok "Sudoers entry removed."

# Kill any stray RepeaterWatch python processes still holding a port
pkill -f "venv/bin/python.*app.py" 2>/dev/null && ok "Stray python process killed." || true

if [[ -d /opt/RepeaterWatch ]]; then
    if yn "Back up the database before removing?" y; then
        DB_BACKUP="/home/${SUDO_USER:-root}/meshcore-db-backup-$(date +%Y%m%d-%H%M%S).db"
        cp /opt/RepeaterWatch/meshcore.db "$DB_BACKUP" 2>/dev/null \
            && ok "Database backed up to: $DB_BACKUP" \
            || warn "No database file found — skipping backup."
    fi
    rm -rf /opt/RepeaterWatch
    ok "/opt/RepeaterWatch removed."
fi

rm -rf /tmp/meshcore-fw
ok "Firmware upload temp dir removed."

if id meshcoremon &>/dev/null; then
    if yn "Remove service user 'meshcoremon'?" y; then
        userdel meshcoremon 2>/dev/null && ok "User 'meshcoremon' removed." || warn "Could not remove user 'meshcoremon' — remove manually with: sudo userdel meshcoremon"
    fi
fi

# ── mctomqtt ──────────────────────────────────────────────────────────────────
header "Removing mctomqtt"

if [[ -f /opt/mctomqtt/uninstall.sh ]]; then
    info "Running mctomqtt's own uninstaller..."
    echo ""
    bash /opt/mctomqtt/uninstall.sh || true
    echo ""
    ok "mctomqtt uninstaller completed."
else
    if systemctl is-active --quiet mctomqtt 2>/dev/null; then
        systemctl stop mctomqtt; ok "mctomqtt stopped."
    fi
    if systemctl is-enabled --quiet mctomqtt 2>/dev/null; then
        systemctl disable mctomqtt; ok "mctomqtt disabled."
    fi
    rm -f /etc/systemd/system/mctomqtt.service
    rm -rf /opt/mctomqtt
    rm -rf /etc/mctomqtt
    ok "mctomqtt removed."
fi

# Remove our systemd override regardless of which path ran
rm -rf /etc/systemd/system/mctomqtt.service.d
systemctl reset-failed mctomqtt 2>/dev/null || true
ok "mctomqtt systemd overrides removed."

# Remove mctomqtt service user if it exists
if id mctomqtt &>/dev/null; then
    userdel mctomqtt 2>/dev/null && ok "User 'mctomqtt' removed." || warn "Could not remove user 'mctomqtt' — remove manually."
fi

# ── SerialMux ─────────────────────────────────────────────────────────────────
header "Removing SerialMux"

if systemctl is-active --quiet SerialMux 2>/dev/null; then
    systemctl stop SerialMux; ok "SerialMux stopped."
fi
if systemctl is-enabled --quiet SerialMux 2>/dev/null; then
    systemctl disable SerialMux; ok "SerialMux disabled."
fi
rm -f /etc/systemd/system/SerialMux.service
systemctl reset-failed SerialMux 2>/dev/null || true
ok "Service file removed."

if [[ -d /opt/SerialMux ]]; then
    rm -rf /opt/SerialMux
    ok "/opt/SerialMux removed."
fi

# Remove virtual port symlinks created by SerialMux
for vport in /dev/ttyV0 /dev/ttyV1 /dev/ttyV2; do
    [[ -L "$vport" ]] && rm -f "$vport" && ok "Removed $vport" || true
done

# ── Reload systemd ────────────────────────────────────────────────────────────
systemctl daemon-reload
ok "systemd daemon reloaded."

# ── Done ──────────────────────────────────────────────────────────────────────
header "Uninstallation Complete"
ok "RepeaterWatch, mctomqtt, and SerialMux have been fully removed."
echo ""

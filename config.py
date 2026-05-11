import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# --- Single-radio legacy env vars (radio A defaults) ---------------------
# These remain as module-level constants so existing code paths that haven't
# been refactored to radio_id-awareness keep working. They always reflect
# radio 'a' (the default / only radio in single-radio mode).

SERIAL_PORT = os.environ.get("MESHCORE_SERIAL_PORT", "/dev/ttyV0")
SERIAL_BAUD = int(os.environ.get("MESHCORE_SERIAL_BAUD", "115200"))
SERIAL_TIMEOUT = float(os.environ.get("MESHCORE_SERIAL_TIMEOUT", "5"))

POLL_INTERVAL_SECS = int(os.environ.get("MESHCORE_POLL_INTERVAL", "300"))

DB_PATH = os.environ.get("MESHCORE_DB_PATH", os.path.join(os.path.dirname(__file__), "meshcore.db"))
RETENTION_DAYS = int(os.environ.get("MESHCORE_RETENTION_DAYS", "30"))

FLASK_HOST = os.environ.get("MESHCORE_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("MESHCORE_PORT", "5000"))
FLASK_DEBUG = os.environ.get("MESHCORE_DEBUG", "0") == "1"

FLASH_SERIAL_PORT = os.environ.get(
    "MESHCORE_FLASH_SERIAL_PORT",
    "/dev/serial/by-id/usb-Seeed_Studio_XIAO_nRF52840_C8A73AB0B3AB137D-if00",
)
FIRMWARE_UPLOAD_DIR = os.environ.get("MESHCORE_FIRMWARE_UPLOAD_DIR", "/tmp/meshcore-fw")

MAX_QUERY_HOURS = 720  # 30 days

SECRET_KEY = os.environ.get("MESHCORE_SECRET_KEY", None)
PASSWORD = os.environ.get("MESHCORE_PASSWORD", None)

# Fail2ban: lock out IPs after too many failed login attempts
LOGIN_MAX_ATTEMPTS = int(os.environ.get("MESHCORE_LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECS = int(os.environ.get("MESHCORE_LOGIN_LOCKOUT_SECS", "300"))

# Trusted reverse proxies (comma-separated IPs, e.g. "127.0.0.1,10.0.0.1")
TRUSTED_PROXIES = os.environ.get("MESHCORE_TRUSTED_PROXIES", "")

TERMINAL_SERIAL_PORT = os.environ.get("MESHCORE_TERMINAL_SERIAL_PORT", "/dev/ttyV2")
TERMINAL_SERIAL_BAUD = int(os.environ.get("MESHCORE_TERMINAL_SERIAL_BAUD", "115200"))

RADIO_RESET_GPIO_PIN = int(os.environ.get("MESHCORE_RADIO_RESET_GPIO", "4"))
USB_RELAY_GPIO_PIN = int(os.environ.get("MESHCORE_USB_RELAY_GPIO", "17"))

SENSOR_POLL_ENABLED = os.environ.get("MESHCORE_SENSOR_POLL", "1") != "0"

# Individual sensor enable/disable (Settings UI writes these to .env)
SENSOR_INA3221_ENABLED = os.environ.get("MESHCORE_SENSOR_INA3221", "1") != "0"
SENSOR_BME280_ENABLED = os.environ.get("MESHCORE_SENSOR_BME280", "1") != "0"
SENSOR_LIS2DW12_ENABLED = os.environ.get("MESHCORE_SENSOR_LIS2DW12", "1") != "0"
SENSOR_AS3935_ENABLED = os.environ.get("MESHCORE_SENSOR_AS3935", "1") != "0"
SENSOR_BQ24074_ENABLED = os.environ.get("MESHCORE_SENSOR_BQ24074", "1") != "0"

AS3935_IRQ_GPIO = int(os.environ.get("MESHCORE_AS3935_IRQ_GPIO", "18"))
AS3935_AFE_MODE = os.environ.get("MESHCORE_AS3935_AFE_MODE", "outdoor")  # "indoor" or "outdoor"
AS3935_NOISE_FLOOR = int(os.environ.get("MESHCORE_AS3935_NOISE_FLOOR", "3"))  # 0-7
AS3935_WATCHDOG = int(os.environ.get("MESHCORE_AS3935_WATCHDOG", "3"))  # 0-15
AS3935_SPIKE_REJECTION = int(os.environ.get("MESHCORE_AS3935_SPIKE_REJECTION", "3"))  # 0-15
AS3935_MASK_DISTURBER = os.environ.get("MESHCORE_AS3935_MASK_DIST", "1") == "1"  # mask disturber events
AS3935_MIN_STRIKES = int(os.environ.get("MESHCORE_AS3935_MIN_STRIKES", "5"))  # 1,5,9,16
AS3935_MIN_DISTANCE = int(os.environ.get("MESHCORE_AS3935_MIN_DISTANCE", "2"))  # km, filter out <= this

BQ24074_CHG_GPIO = int(os.environ.get("MESHCORE_BQ24074_CHG_GPIO", "19"))
BQ24074_PGOOD_GPIO = int(os.environ.get("MESHCORE_BQ24074_PGOOD_GPIO", "13"))
BQ24074_CE_GPIO = int(os.environ.get("MESHCORE_BQ24074_CE_GPIO", "6"))


# --- Dual-radio config ---------------------------------------------------
# RepeaterWatch can host a single radio (default) or two radios on one Pi
# (cross-band repeater). Toggle via MESHCORE_DUAL_RADIO_MODE=1.
#
# Schema: RADIOS is a list of dicts, each with:
#   id                    short identifier used in URLs, MQTT routing, and the
#                         radio_id column on DB tables. "a" / "b".
#   label                 human-readable label shown in the dashboard tab.
#   serial_port           SerialMux virtual port for stats/commands (ttyV0*).
#   flash_serial_port     /dev/serial/by-id/... path used during DFU flash.
#   terminal_serial_port  SerialMux virtual port exposed to the web terminal.
#   reset_gpio_pin        GPIO pin pulsed to reset / enter bootloader.
#   usb_relay_gpio_pin    GPIO pin controlling the radio's USB power relay.
#   iata                  IATA-style site code used by mctomqtt — must be
#                         distinct per radio in dual mode (e.g. FH1A/FH1B).

DUAL_RADIO_MODE = os.environ.get("MESHCORE_DUAL_RADIO_MODE", "0") == "1"


def _radio_a_config():
    """Build radio A config from legacy single-radio env vars."""
    return {
        "id": "a",
        "label": os.environ.get("MESHCORE_RADIO_A_LABEL", "Radio"),
        "serial_port": SERIAL_PORT,
        "serial_baud": SERIAL_BAUD,
        "flash_serial_port": FLASH_SERIAL_PORT,
        "terminal_serial_port": TERMINAL_SERIAL_PORT,
        "terminal_serial_baud": TERMINAL_SERIAL_BAUD,
        "reset_gpio_pin": RADIO_RESET_GPIO_PIN,
        "usb_relay_gpio_pin": USB_RELAY_GPIO_PIN,
        "iata": os.environ.get("MESHCORE_IATA_A", os.environ.get("MESHCORE_IATA", "")),
    }


def _radio_b_config():
    """Build radio B config from MESHCORE_*_B env vars. Only loaded when
    DUAL_RADIO_MODE=1. GPIO pins have no fallback — operator must allocate
    distinct pins from radio A (default A=reset:4, relay:17)."""
    reset_pin = os.environ.get("MESHCORE_RADIO_RESET_GPIO_B")
    relay_pin = os.environ.get("MESHCORE_USB_RELAY_GPIO_B")
    return {
        "id": "b",
        "label": os.environ.get("MESHCORE_RADIO_B_LABEL", "Radio B"),
        "serial_port": os.environ.get("MESHCORE_SERIAL_PORT_B", "/dev/ttyV0b"),
        "serial_baud": int(os.environ.get("MESHCORE_SERIAL_BAUD_B", str(SERIAL_BAUD))),
        "flash_serial_port": os.environ.get("MESHCORE_FLASH_SERIAL_PORT_B", ""),
        "terminal_serial_port": os.environ.get("MESHCORE_TERMINAL_SERIAL_PORT_B", "/dev/ttyV2b"),
        "terminal_serial_baud": int(os.environ.get("MESHCORE_TERMINAL_SERIAL_BAUD_B", str(TERMINAL_SERIAL_BAUD))),
        "reset_gpio_pin": int(reset_pin) if reset_pin else None,
        "usb_relay_gpio_pin": int(relay_pin) if relay_pin else None,
        "iata": os.environ.get("MESHCORE_IATA_B", ""),
    }


RADIOS = [_radio_a_config()]
if DUAL_RADIO_MODE:
    RADIOS.append(_radio_b_config())


def get_radio(radio_id: str):
    """Look up a radio's config dict by id ('a' / 'b'). Returns None if not configured."""
    for r in RADIOS:
        if r["id"] == radio_id:
            return r
    return None

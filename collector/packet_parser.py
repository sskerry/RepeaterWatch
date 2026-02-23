from __future__ import annotations

import re
import struct
import logging

logger = logging.getLogger(__name__)

# Matches info lines like:
#   U: RX, len=113 (type=4, route=D, payload_len=111) SNR=11 RSSI=-26 score=1000 time=395 hash=37F3A6C9C6D3704E
#   U: TX, len=70 (type=1, route=D, payload_len=68) [77 -> C8]
_INFO_RE = re.compile(
    r"(TX|RX), len=(\d+) \(type=(\d+), route=(\w+), payload_len=(\d+)\)"
    r"(?: SNR=([-\d]+))?"
    r"(?: RSSI=([-\d]+))?"
    r"(?: score=([-\d]+))?"
    r"(?: time=(\d+))?"
    r"(?: hash=(\w+))?"
)

# Matches RAW hex lines like:
#   U RAW: 12008482E61880C65C134BA87444...
_RAW_RE = re.compile(r"U RAW: ([0-9A-Fa-f]+)")

DEVICE_ROLES = {1: "Chat", 2: "Repeater", 3: "Room", 4: "Sensor"}


def parse_info_line(line: str) -> dict | None:
    m = _INFO_RE.search(line)
    if not m:
        return None
    return {
        "direction": m.group(1),
        "length": int(m.group(2)),
        "type": int(m.group(3)),
        "route": m.group(4),
        "payload_len": int(m.group(5)),
        "snr": float(m.group(6)) if m.group(6) else None,
        "rssi": float(m.group(7)) if m.group(7) else None,
        "score": float(m.group(8)) if m.group(8) else None,
        "time": int(m.group(9)) if m.group(9) else None,
        "hash": m.group(10),
    }


def extract_raw_hex(line: str) -> str | None:
    m = _RAW_RE.search(line)
    return m.group(1) if m else None


def decode_advert(raw_hex: str) -> dict | None:
    try:
        data = bytes.fromhex(raw_hex)
    except ValueError:
        return None

    if len(data) < 3:
        return None

    header = data[0]
    payload_type = (header >> 2) & 0x0F
    if payload_type != 4:
        return None

    # Skip header byte, then path_len byte + path data
    path_len = data[1]
    payload_start = 2 + path_len
    payload = data[payload_start:]

    # Advert needs at least 101 bytes (32 pubkey + 4 ts + 64 sig + 1 flags)
    if len(payload) < 101:
        return None

    pubkey = payload[0:32].hex()
    timestamp = struct.unpack_from("<I", payload, 32)[0]
    flags = payload[100]

    device_role = flags & 0x0F
    has_location = bool(flags & 0x10)
    has_feature1 = bool(flags & 0x20)
    has_feature2 = bool(flags & 0x40)
    has_name = bool(flags & 0x80)

    offset = 101
    lat = None
    lon = None
    name = None

    if has_location:
        if offset + 8 > len(payload):
            return None
        lat_raw = struct.unpack_from("<i", payload, offset)[0]
        lon_raw = struct.unpack_from("<i", payload, offset + 4)[0]
        lat = lat_raw / 1_000_000.0
        lon = lon_raw / 1_000_000.0
        offset += 8

    if has_feature1:
        offset += 2

    if has_feature2:
        offset += 2

    if has_name:
        name_bytes = payload[offset:]
        name = name_bytes.split(b"\x00")[0].decode("utf-8", errors="replace")

    return {
        "pubkey_prefix": pubkey[:16],
        "pubkey_full": pubkey,
        "timestamp": timestamp,
        "device_role": device_role,
        "device_role_name": DEVICE_ROLES.get(device_role, "Unknown"),
        "lat": lat,
        "lon": lon,
        "name": name,
    }

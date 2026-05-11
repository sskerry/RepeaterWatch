import logging

from database import models

logger = logging.getLogger(__name__)

STARTUP_COMMANDS = [
    ("get name", "name"),
    ("get public.key", "public_key"),
    ("get radio", "radio_config"),
    ("get lat", "lat"),
    ("get lon", "lon"),
    ("ver", "firmware"),
    ("board", "board"),
]


ERROR_RESPONSES = {"unknown command", "error", "invalid"}


def collect_device_info(reader, radio_id: str = 'a'):
    for cmd, key in STARTUP_COMMANDS:
        resp = reader.send_command(cmd)
        if resp:
            # Take only the first line to avoid unsolicited serial
            # output bleeding into the value.
            value = resp.strip().split("\n", 1)[0].strip()
            if value.startswith("> "):
                value = value[2:]
            if value.lower() in ERROR_RESPONSES:
                logger.warning("Command '%s' not supported: %s", cmd, value)
                continue
            models.set_device_info(key, value, radio_id=radio_id)
            logger.info("Device %s (radio %s): %s", key, radio_id, value)
        else:
            logger.warning("No response for startup command: %s", cmd)


def claim_or_verify_identity(radio_id: str) -> dict:
    """Compare the live public_key (already written by collect_device_info) against
    the stored claimed_pubkey for this radio.

    On first boot, claim the live key.  On subsequent boots, verify it matches.
    On mismatch, log CRITICAL but do NOT abort the poller — the operator chose
    warn-not-fail-closed (handoff decision Q2 for the dashboard/logging path).
    Flash blocking is handled separately in firmware_flasher._flash_worker.

    Returns:
        dict with keys:
          "status":        "claimed" | "verified" | "mismatch" | "unknown"
          "live_pubkey":   str | None
          "claimed_pubkey": str | None
    """
    info = models.get_device_info(radio_id=radio_id)
    live_pubkey = info.get("public_key") or None

    if not live_pubkey:
        logger.debug("Radio %s: no live public_key available yet — identity unknown.", radio_id)
        return {"status": "unknown", "live_pubkey": None, "claimed_pubkey": None}

    claimed_pubkey = info.get("claimed_pubkey") or None

    if not claimed_pubkey:
        # First boot — claim the current key.
        models.set_device_info("claimed_pubkey", live_pubkey, radio_id=radio_id)
        logger.info(
            "Radio %s: identity claimed — public_key prefix %s.",
            radio_id, live_pubkey[:4].upper(),
        )
        return {"status": "claimed", "live_pubkey": live_pubkey, "claimed_pubkey": live_pubkey}

    if claimed_pubkey == live_pubkey:
        logger.debug("Radio %s: identity verified (prefix %s).", radio_id, live_pubkey[:4].upper())
        return {"status": "verified", "live_pubkey": live_pubkey, "claimed_pubkey": claimed_pubkey}

    # Mismatch — log CRITICAL with prefix/suffix of each key (not full keys).
    logger.critical(
        "Radio %s identity MISMATCH: claimed=%s...%s, live=%s...%s  "
        "Was this radio replaced or rewired? Reclaim via the dashboard if intentional.",
        radio_id,
        claimed_pubkey[:4].upper(), claimed_pubkey[-4:].upper(),
        live_pubkey[:4].upper(), live_pubkey[-4:].upper(),
    )
    return {"status": "mismatch", "live_pubkey": live_pubkey, "claimed_pubkey": claimed_pubkey}

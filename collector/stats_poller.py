from __future__ import annotations

import logging
import os
import threading
import time

import config

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from database import models
from database.retention import purge_old_data
from database.schema import init_db
from collector.packet_parser import parse_info_line, decode_advert
from collector.serial_reader import SerialReader
from collector.startup import collect_device_info, claim_or_verify_identity

logger = logging.getLogger(__name__)


class StatsPoller:
    def __init__(self):
        # Build one SerialReader per radio in config.RADIOS
        self.readers: dict[str, SerialReader] = {}
        for r in config.RADIOS:
            self.readers[r["id"]] = SerialReader(
                port=r["serial_port"],
                baud=r["serial_baud"],
                timeout=config.SERIAL_TIMEOUT,
                radio_id=r["id"],
            )

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Per-reader tracking
        self._last_poll: dict[str, float] = {rid: 0 for rid in self.readers}
        self._poll_count: dict[str, int] = {rid: 0 for rid in self.readers}
        self._error_count: dict[str, int] = {rid: 0 for rid in self.readers}
        # Per-radio identity status (populated after first collect_device_info run)
        self.identity_status: dict[str, dict] = {}

    @property
    def status(self) -> dict:
        radios = {}
        for rid, reader in self.readers.items():
            radios[rid] = {
                "serial_connected": reader.connected,
                "serial_port": reader._port_name,
                "last_poll": self._last_poll.get(rid, 0),
                "poll_count": self._poll_count.get(rid, 0),
                "error_count": self._error_count.get(rid, 0),
            }
        return {
            "running": self._thread is not None and self._thread.is_alive(),
            "radios": radios,
            # Backward-compat: expose radio 'a' fields at top level
            "serial_connected": self.readers["a"].connected if "a" in self.readers else False,
            "serial_port": self.readers["a"]._port_name if "a" in self.readers else config.SERIAL_PORT,
            "last_poll": self._last_poll.get("a", 0),
            "poll_count": self._poll_count.get("a", 0),
            "error_count": self._error_count.get("a", 0),
        }

    def start(self):
        self._stop_event.clear()
        for reader in self.readers.values():
            reader.set_packet_callback(self._on_packet)
        self._thread = threading.Thread(target=self._run, daemon=True, name="stats-poller")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        for reader in self.readers.values():
            reader.disconnect()

    def disconnect_reader(self, radio_id: str) -> bool:
        """Disconnect a single reader without stopping the poll loop.

        Returns True if the reader existed and was disconnected.
        """
        reader = self.readers.get(radio_id)
        if reader is None:
            return False
        reader.disconnect()
        return True

    def reconnect_reader(self, radio_id: str) -> bool:
        """Reconnect a single previously-disconnected reader.

        Returns True if the reader existed and connected successfully.
        The poll loop will see reader.connected==False and call
        _connect_with_retry on its own, but callers who want immediate
        reconnection can call this directly.
        """
        reader = self.readers.get(radio_id)
        if reader is None:
            return False
        for attempt in range(3):
            if reader.connect():
                return True
            logger.warning(
                "Reconnect attempt %d failed for radio %s", attempt + 1, radio_id
            )
            time.sleep(2)
        return False

    def reset_radio(self, radio_id: str) -> bool:
        """Disconnect reader, pulse reset GPIO for the named radio, reconnect.

        This is the thin orchestration helper so route handlers stay thin.
        Returns True on success.  GPIO errors are logged but not re-raised so
        the poller stays running even on a GPIO-unavailable dev machine.
        """
        from collector import radio_gpio
        radio = config.get_radio(radio_id)
        if radio is None:
            logger.error("reset_radio: unknown radio_id %s", radio_id)
            return False

        self.disconnect_reader(radio_id)
        try:
            radio_gpio.reset_radio(pin=radio.get("reset_gpio_pin"))
        except Exception:
            logger.exception("GPIO reset failed for radio %s", radio_id)

        time.sleep(2)
        self.reconnect_reader(radio_id)
        return True

    def bootloader_radio(self, radio_id: str) -> bool:
        """Disconnect reader, pulse bootloader GPIO for the named radio.

        Does NOT reconnect — the radio is in DFU mode and the serial port
        won't be available until firmware is flashed and the radio reboots.
        Returns True on success.
        """
        from collector import radio_gpio
        radio = config.get_radio(radio_id)
        if radio is None:
            logger.error("bootloader_radio: unknown radio_id %s", radio_id)
            return False

        self.disconnect_reader(radio_id)
        try:
            radio_gpio.bootloader_mode(pin=radio.get("reset_gpio_pin"))
        except Exception:
            logger.exception("GPIO bootloader failed for radio %s", radio_id)
        return True

    def get_identity_status(self, radio_id: str) -> dict:
        """Return the most recent identity-check result for radio_id.

        Returns an 'unknown' sentinel dict if the radio has not yet been
        through a collect_device_info + claim_or_verify_identity cycle.
        """
        return self.identity_status.get(
            radio_id,
            {"status": "unknown", "live_pubkey": None, "claimed_pubkey": None},
        )

    def reclaim_identity(self, radio_id: str) -> bool:
        """Overwrite the stored claimed_pubkey with the current live public_key.

        Called by the /identity/reclaim API endpoint when the operator confirms
        a radio swap was intentional.  Returns False if no live pubkey is
        available (radio not yet polled).
        """
        live_pubkey = models.get_device_info(radio_id=radio_id).get("public_key") or ""
        if not live_pubkey:
            return False
        models.set_device_info("claimed_pubkey", live_pubkey, radio_id=radio_id)
        self.identity_status[radio_id] = {
            "status": "verified",
            "live_pubkey": live_pubkey,
            "claimed_pubkey": live_pubkey,
        }
        logger.info(
            "Radio %s: identity reclaimed — new claimed_pubkey prefix %s.",
            radio_id, live_pubkey[:4].upper(),
        )
        return True

    def _run(self):
        # Connect all readers with retry
        for reader in self.readers.values():
            self._connect_with_retry(reader)

        # Device info + initial background line drain for connected readers
        for rid, reader in self.readers.items():
            if reader.connected:
                time.sleep(2)
                reader.read_background_lines()
                collect_device_info(reader, radio_id=rid)
                # Identity claim/verify runs immediately after device info is stored (L3.3)
                self.identity_status[rid] = claim_or_verify_identity(rid)

        while not self._stop_event.is_set():
            ts = models.aligned_ts()

            # Pi health — always collect once per cycle (Pi-wide, not per-radio)
            self._poll_pi_health(ts)

            # Per-radio serial polling
            for rid, reader in self.readers.items():
                if not reader.connected:
                    self._connect_with_retry(reader)

                if reader.connected:
                    try:
                        self._poll_serial(ts, rid, reader)
                        self._last_poll[rid] = time.time()
                        self._poll_count[rid] = self._poll_count.get(rid, 0) + 1
                    except Exception:
                        logger.exception("Error during poll cycle for radio %s", rid)
                        self._error_count[rid] = self._error_count.get(rid, 0) + 1

            # Purge old data once per cycle
            try:
                conn = init_db(config.DB_PATH)
                purge_old_data(conn)
                conn.close()
            except Exception:
                logger.exception("Error during retention purge")

            self._wait_next_cycle()

    def _connect_with_retry(self, reader: SerialReader):
        for attempt in range(3):
            if reader.connect():
                return
            logger.warning(
                "Connection attempt %d failed for radio %s, retrying...",
                attempt + 1, reader.radio_id,
            )
            time.sleep(5)

    def _wait_next_cycle(self):
        next_ts = models.aligned_ts(time.time() + config.POLL_INTERVAL_SECS)
        while not self._stop_event.is_set():
            remaining = next_ts - time.time()
            if remaining <= 0:
                break
            self._stop_event.wait(min(remaining, 5))
            for reader in self.readers.values():
                reader.read_background_lines()

    def _poll_serial(self, ts: int, radio_id: str, reader: SerialReader):
        # stats-core
        data = reader.send_command_json("stats-core")
        if data:
            models.insert_stats_core(
                ts,
                battery_mv=data.get("battery_mv"),
                uptime_secs=data.get("uptime_secs"),
                errors=data.get("errors"),
                queue_len=data.get("queue_len"),
                radio_id=radio_id,
            )

        # stats-radio
        data = reader.send_command_json("stats-radio")
        if data:
            # AGC resets in firmware 1.14.x briefly zero out the noise floor
            # register (0x0000 → 0 dBm).  A real 0 dBm reading is physically
            # impossible on LoRa hardware, so treat it as missing data.
            raw_nf = data.get("noise_floor")
            noise_floor = raw_nf if raw_nf is not None and raw_nf != 0 else None
            models.insert_stats_radio(
                ts,
                noise_floor=noise_floor,
                tx_air_secs=data.get("tx_air_secs"),
                rx_air_secs=data.get("rx_air_secs"),
                last_rssi=data.get("last_rssi"),
                last_snr=data.get("last_snr"),
                radio_id=radio_id,
            )

        # stats-packets
        data = reader.send_command_json("stats-packets")
        if data:
            models.insert_stats_packets(
                ts,
                recv_total=data.get("recv") or data.get("recv_total"),
                sent_total=data.get("sent") or data.get("sent_total"),
                recv_errors=data.get("recv_errors"),
                fwd_total=data.get("fwd_total"),
                fwd_errors=data.get("fwd_errors"),
                direct_dups=data.get("direct_dups"),
                flood_dups=data.get("flood_dups"),
                direct_tx=data.get("direct_tx"),
                flood_tx=data.get("flood_tx"),
                direct_rx=data.get("direct_rx"),
                flood_rx=data.get("flood_rx"),
                radio_id=radio_id,
            )

        # stats-extpower (only when using INA3221 power source)
        if models.get_setting("power_source", "ina3221") != "ina3221":
            return
        data = reader.send_command_json("stats-extpower")
        if data:
            channels = []
            for ch_num in range(1, 4):
                v_mv = data.get(f"ch{ch_num}_voltage_mv")
                i_ma = data.get(f"ch{ch_num}_current_ma")
                v = v_mv / 1000.0 if v_mv is not None else None
                i = i_ma if i_ma is not None else None
                p = (v_mv * i_ma / 1000.0) if v_mv is not None and i_ma is not None else None
                channels.append({"voltage": v, "current": i, "power": p})
            models.insert_stats_extpower(ts, channels)

    def _poll_pi_health(self, ts: int):
        if not HAS_PSUTIL:
            return
        try:
            cpu_pct = psutil.cpu_percent(interval=1)
            load_1, load_5, load_15 = os.getloadavg()
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            cpu_temp = None
            temps = psutil.sensors_temperatures()
            if temps:
                for key in ("cpu_thermal", "cpu-thermal", "coretemp"):
                    if key in temps and temps[key]:
                        cpu_temp = temps[key][0].current
                        break

            disk = psutil.disk_usage("/")
            disk_io = psutil.disk_io_counters()
            net_io = psutil.net_io_counters()
            uptime = int(time.time() - psutil.boot_time())
            proc_count = len(psutil.pids())

            models.insert_stats_pi_health(
                ts,
                cpu_percent=cpu_pct,
                load_1=round(load_1, 2),
                load_5=round(load_5, 2),
                load_15=round(load_15, 2),
                mem_used_mb=round(mem.used / 1048576, 1),
                mem_total_mb=round(mem.total / 1048576, 1),
                mem_percent=mem.percent,
                swap_used_mb=round(swap.used / 1048576, 1),
                swap_total_mb=round(swap.total / 1048576, 1),
                cpu_temp=cpu_temp,
                disk_used_gb=round(disk.used / 1073741824, 2),
                disk_total_gb=round(disk.total / 1073741824, 2),
                disk_percent=disk.percent,
                disk_read_bytes=disk_io.read_bytes if disk_io else None,
                disk_write_bytes=disk_io.write_bytes if disk_io else None,
                net_bytes_sent=net_io.bytes_sent if net_io else None,
                net_bytes_recv=net_io.bytes_recv if net_io else None,
                uptime_secs=uptime,
                process_count=proc_count,
            )

            # Per-device disk IO — only physical disks we care about
            perdisk = psutil.disk_io_counters(perdisk=True)
            if perdisk:
                for dev in ("mmcblk0", "sda"):
                    if dev in perdisk:
                        c = perdisk[dev]
                        models.insert_disk_io(ts, dev, c.read_bytes, c.write_bytes)
        except Exception:
            logger.exception("Error collecting Pi health metrics")

    def _on_packet(self, info_line: str, raw_hex: str | None, radio_id: str = 'a'):
        parsed = parse_info_line(info_line)
        if not parsed:
            return

        ts = int(time.time())

        # Log every packet
        models.insert_packet(
            ts,
            direction=parsed["direction"],
            pkt_type=parsed["type"],
            route=parsed["route"],
            snr=parsed["snr"],
            rssi=parsed["rssi"],
            score=parsed["score"],
            hash_=parsed["hash"],
            raw_hex=raw_hex,
            radio_id=radio_id,
        )

        # Decode adverts (type=4) for neighbor tracking
        # Only Repeaters (2) and Room Servers (3) count as neighbors
        if parsed["type"] == 4 and raw_hex:
            advert = decode_advert(raw_hex)
            if advert and advert["device_role"] in (2, 3):
                # Only track direct (0-hop) RX adverts as neighbors
                if parsed["direction"] == "RX" and parsed["route"] == "D":
                    models.upsert_neighbor(
                        pubkey_prefix=advert["pubkey_prefix"],
                        name=advert["name"],
                        device_role=advert["device_role_name"],
                        last_seen=ts,
                        last_snr=parsed["snr"],
                        last_rssi=parsed["rssi"],
                        lat=advert["lat"],
                        lon=advert["lon"],
                        radio_id=radio_id,
                    )
                    models.insert_neighbor_sighting(
                        models.aligned_ts(ts),
                        advert["pubkey_prefix"],
                        snr=parsed["snr"],
                        rssi=parsed["rssi"],
                        radio_id=radio_id,
                    )
                    logger.info(
                        "Neighbor (radio %s): %s (%s) SNR=%s lat=%s lon=%s",
                        radio_id, advert["name"], advert["device_role_name"],
                        parsed["snr"], advert["lat"], advert["lon"],
                    )

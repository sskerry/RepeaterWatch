from __future__ import annotations

import json
import logging
import threading
import time

import serial

import config

logger = logging.getLogger(__name__)


class SerialReader:
    def __init__(self):
        self._port: serial.Serial | None = None
        self._lock = threading.Lock()
        self._connected = False
        self._packet_callback = None
        self._last_raw_hex: str | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def set_packet_callback(self, cb):
        """Callback signature: cb(info_line: str, raw_hex: str | None)"""
        self._packet_callback = cb

    def connect(self) -> bool:
        try:
            self._port = serial.Serial(
                port=config.SERIAL_PORT,
                baudrate=config.SERIAL_BAUD,
                timeout=config.SERIAL_TIMEOUT,
            )
            self._connected = True
            logger.info("Connected to %s at %d baud", config.SERIAL_PORT, config.SERIAL_BAUD)
            return True
        except (serial.SerialException, OSError, Exception) as e:
            logger.error("Failed to connect to %s: %s", config.SERIAL_PORT, e)
            self._connected = False
            return False

    def disconnect(self):
        if self._port and self._port.is_open:
            self._port.close()
        self._connected = False

    def send_command(self, command: str, timeout: float | None = None) -> str | None:
        if not self._port or not self._port.is_open:
            logger.warning("Serial port not open, cannot send: %s", command)
            return None

        with self._lock:
            try:
                # Drain and process any pending lines before sending
                self._drain_pending()
                self._port.write(f"{command}\r\n".encode())
                return self._read_response(timeout or config.SERIAL_TIMEOUT)
            except serial.SerialException as e:
                logger.error("Serial error sending '%s': %s", command, e)
                self._connected = False
                return None

    def _drain_pending(self):
        """Read and dispatch any lines waiting in the serial buffer."""
        saved_timeout = self._port.timeout
        self._port.timeout = 0.05
        try:
            while self._port.in_waiting:
                raw = self._port.readline()
                if raw:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        self._dispatch_line(line)
        except serial.SerialException:
            pass
        finally:
            self._port.timeout = saved_timeout

    def _read_response(self, timeout: float) -> str:
        lines = []
        deadline = time.monotonic() + timeout
        capture = False

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._port.timeout = min(remaining, 0.5)
            raw = self._port.readline()
            if not raw:
                if capture and lines:
                    break
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            if line.startswith("-> "):
                capture = True
                content = line[3:]
                if content:
                    lines.append(content)
                    # Single-line response complete; stop capturing so
                    # unsolicited output doesn't bleed into the value.
                    break
                continue

            if capture:
                lines.append(line)
            else:
                self._dispatch_line(line)

        return "\n".join(lines)

    def _dispatch_line(self, line: str):
        """Handle a non-response line: buffer RAW hex, dispatch info lines."""
        if "U RAW:" in line:
            from collector.packet_parser import extract_raw_hex
            self._last_raw_hex = extract_raw_hex(line)
            return

        if "U:" in line and ("TX," in line or "RX," in line):
            if self._packet_callback:
                self._packet_callback(line, self._last_raw_hex)
            self._last_raw_hex = None

    def send_command_json(self, command: str) -> dict | None:
        raw = self.send_command(command)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Non-JSON response for '%s': %s", command, raw[:200])
            return None

    def read_background_lines(self):
        if not self._port or not self._port.is_open:
            return
        try:
            while self._port.in_waiting:
                raw = self._port.readline()
                if raw:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        self._dispatch_line(line)
        except serial.SerialException:
            pass

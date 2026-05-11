import logging
import os
import pty
import select
import signal
import threading
import time

import serial

import config

logger = logging.getLogger(__name__)


def _open_serial_for_radio(radio_id: str):
    """Return (serial.Serial, error_str) for the named radio's terminal port.

    error_str is None on success.
    """
    radio = config.get_radio(radio_id)
    if radio is None:
        return None, f"Unknown radio: {radio_id!r}"
    port = radio.get("terminal_serial_port", "")
    baud = radio.get("terminal_serial_baud", config.TERMINAL_SERIAL_BAUD)
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=0)
        return ser, None
    except Exception as e:
        return None, f"Error opening {port}: {e}"


def register_terminal_routes(sock):

    @sock.route("/ws/terminal/pty")
    def terminal_pty(ws):
        child_pid, master_fd = pty.fork()

        if child_pid == 0:
            os.environ.clear()
            os.environ["TERM"] = "xterm-256color"
            os.environ["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            os.execv("/bin/login", ["/bin/login"])

        stop = threading.Event()

        def reader():
            try:
                while not stop.is_set():
                    r, _, _ = select.select([master_fd], [], [], 0.1)
                    if r:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        ws.send(data)
            except Exception:
                pass

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        try:
            while True:
                data = ws.receive()
                if data is None:
                    break
                if isinstance(data, str):
                    data = data.encode()
                os.write(master_fd, data)
        except Exception:
            pass
        finally:
            stop.set()
            try:
                os.kill(child_pid, signal.SIGHUP)
                os.waitpid(child_pid, 0)
            except Exception:
                pass
            try:
                os.close(master_fd)
            except OSError:
                pass
            reader_thread.join(timeout=2)

    def _run_serial_ws(ws, ser):
        """Run the serial-bridge loop for an already-opened serial port."""
        stop = threading.Event()

        def reader():
            try:
                while not stop.is_set():
                    if ser.in_waiting:
                        data = ser.read(ser.in_waiting)
                        if data:
                            ws.send(data)
                    else:
                        time.sleep(0.05)
            except Exception:
                pass

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        try:
            while True:
                data = ws.receive()
                if data is None:
                    break
                if isinstance(data, str):
                    data = data.encode()
                ser.write(data)
        except Exception:
            pass
        finally:
            stop.set()
            try:
                ser.close()
            except Exception:
                pass
            reader_thread.join(timeout=2)

    @sock.route("/ws/terminal/serial")
    def terminal_serial(ws):
        """Legacy single-radio serial terminal — uses radio 'a' port."""
        try:
            ser = serial.Serial(
                port=config.TERMINAL_SERIAL_PORT,
                baudrate=config.TERMINAL_SERIAL_BAUD,
                timeout=0,
            )
        except Exception as e:
            ws.send(f"\r\nError opening {config.TERMINAL_SERIAL_PORT}: {e}\r\n")
            return
        _run_serial_ws(ws, ser)

    @sock.route("/ws/terminal/serial/<radio_id>")
    def terminal_serial_radio(ws, radio_id):
        """Per-radio serial terminal — opens the named radio's terminal port."""
        ser, err = _open_serial_for_radio(radio_id)
        if err:
            ws.send(f"\r\n{err}\r\n")
            return
        _run_serial_ws(ws, ser)

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

    @sock.route("/ws/terminal/serial")
    def terminal_serial(ws):
        try:
            ser = serial.Serial(
                port=config.TERMINAL_SERIAL_PORT,
                baudrate=config.TERMINAL_SERIAL_BAUD,
                timeout=0,
            )
        except Exception as e:
            ws.send(f"\r\nError opening {config.TERMINAL_SERIAL_PORT}: {e}\r\n")
            return

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

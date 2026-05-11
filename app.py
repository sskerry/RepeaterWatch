import bcrypt as _bc, secrets as _secrets
import logging
import os
import signal
import sys
import threading
import time

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_sock import Sock
from flask_wtf.csrf import CSRFProtect

import config
# Methods that require authentication even on public installs
_WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
from database.schema import init_db
from database import models
from api.routes import api
from api.terminal import register_terminal_routes
from collector.stats_poller import StatsPoller
from collector.sensor_poller import SensorPoller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Port-stability registry (populated once at startup) ──────────
# Keyed by radio_id → {"flash_serial_port_stable": bool,
#                      "terminal_serial_port_stable": bool,
#                      "stable": bool}
_port_stability: dict = {}


def get_port_stability(radio_id: str) -> dict:
    """Return the port-stability record for a radio_id, or a fully-stable
    sentinel if the radio is unknown (so callers always get a usable dict)."""
    return _port_stability.get(
        radio_id,
        {"flash_serial_port_stable": True, "terminal_serial_port_stable": True, "stable": True},
    )


# Path prefixes that are considered hardware-stable. A path is stable if it
# either points to a USB device by its burnt-in serial number (/dev/serial/by-id/)
# or addresses a fixed on-board UART that the kernel always names the same
# (ttyAMA* for the Pi's PL011, ttyS* for the generic 8250-style serial driver,
# ttyAML* for some Amlogic SoCs). These are wired to dedicated pins, not
# enumerated by USB, so they don't swap on reboot.
_STABLE_PORT_PREFIXES = (
    "/dev/serial/by-id/",
    "/dev/ttyAMA",
    "/dev/ttyAML",
    "/dev/ttyS",
)


def _is_stable_port(path: str) -> bool:
    return path.startswith(_STABLE_PORT_PREFIXES)


def _validate_port_stability() -> None:
    """Check each radio's flash_serial_port and terminal_serial_port.

    A path is considered stable if it's either /dev/serial/by-id/... (USB
    by-id) or a built-in UART (ttyAMA*/ttyAML*/ttyS*). Kernel-assigned USB
    names (ttyACM*, ttyUSB*) are flagged — they can swap on enumeration order.
    The virtual serial_port (ttyV*) is intentionally excluded — it is NOT a
    by-id path and that is correct.
    """
    global _port_stability
    for radio in config.RADIOS:
        rid = radio["id"]
        flash_ok = True
        terminal_ok = True

        flash_port = radio.get("flash_serial_port", "")
        if flash_port and not _is_stable_port(flash_port):
            flash_ok = False
            logger.error(
                "Radio %s: flash_serial_port = %r uses an UNSTABLE kernel-assigned path. "
                "USB enumeration order can swap this across reboots, causing the wrong "
                "physical radio to be targeted. Use /dev/serial/by-id/... (USB) or a "
                "built-in UART like /dev/ttyAMA0 (Pi GPIO) instead.",
                rid, flash_port,
            )

        terminal_port = radio.get("terminal_serial_port", "")
        if terminal_port and not _is_stable_port(terminal_port):
            # ttyV* virtual ports are intentionally not by-id — only flag real device paths
            if not terminal_port.startswith("/dev/ttyV"):
                terminal_ok = False
                logger.error(
                    "Radio %s: terminal_serial_port = %r uses an UNSTABLE kernel-assigned path. "
                    "USB enumeration order can swap this across reboots, causing the wrong "
                    "physical radio to be targeted. Use /dev/serial/by-id/... (USB) or a "
                    "built-in UART like /dev/ttyAMA0 (Pi GPIO) instead.",
                    rid, terminal_port,
                )

        _port_stability[rid] = {
            "flash_serial_port_stable": flash_ok,
            "terminal_serial_port_stable": terminal_ok,
            "stable": flash_ok and terminal_ok,
        }


# ── Fail2ban: track failed login attempts by IP ──────────
_login_attempts = {}   # ip -> [timestamp, timestamp, ...]
_login_lock = threading.Lock()


def _client_ip():
    """Get the real client IP, respecting trusted proxies."""
    # If behind a trusted proxy, use X-Forwarded-For
    if config.TRUSTED_PROXIES:
        trusted = {p.strip() for p in config.TRUSTED_PROXIES.split(",") if p.strip()}
        if request.remote_addr in trusted:
            forwarded = request.headers.get("X-Forwarded-For", "")
            if forwarded:
                # First IP in X-Forwarded-For is the real client
                return forwarded.split(",")[0].strip()
    return request.remote_addr


def _is_locked_out(ip):
    """Check if an IP is currently locked out."""
    with _login_lock:
        attempts = _login_attempts.get(ip, [])
        if len(attempts) < config.LOGIN_MAX_ATTEMPTS:
            return False
        # Check if the most recent attempt is within the lockout window
        cutoff = time.time() - config.LOGIN_LOCKOUT_SECS
        recent = [t for t in attempts if t > cutoff]
        _login_attempts[ip] = recent
        return len(recent) >= config.LOGIN_MAX_ATTEMPTS


def _record_failed_attempt(ip):
    """Record a failed login attempt for an IP."""
    with _login_lock:
        if ip not in _login_attempts:
            _login_attempts[ip] = []
        _login_attempts[ip].append(time.time())
        # Keep only recent attempts to avoid memory leak
        cutoff = time.time() - config.LOGIN_LOCKOUT_SECS
        _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]
    count = len(_login_attempts.get(ip, []))
    logger.warning("Failed login attempt %d/%d from %s", count, config.LOGIN_MAX_ATTEMPTS, ip)


def _clear_attempts(ip):
    """Clear failed attempts after successful login."""
    with _login_lock:
        _login_attempts.pop(ip, None)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY or os.urandom(24)

    # Harden session cookies
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
    if config.TRUSTED_PROXIES:
        # If behind a proxy, assume HTTPS termination
        app.config["SESSION_COOKIE_SECURE"] = True

    # CSRF protection — rejects POST/PUT/DELETE/PATCH without a valid token.
    # JavaScript reads the token from a <meta> tag and sends it as X-CSRFToken.
    csrf = CSRFProtect(app)

    # Limit upload size to 16MB (firmware .zip files are typically ~500KB)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    # Apply ProxyFix if trusted proxies are configured
    if config.TRUSTED_PROXIES:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        logger.info("ProxyFix enabled for trusted proxies: %s", config.TRUSTED_PROXIES)

    # Initialize database
    init_db(config.DB_PATH)
    models.init(config.DB_PATH)

    # Validate port-path stability for all configured radios (L2.1)
    _validate_port_stability()
    # Make the stability map available to route handlers via current_app.config
    app.config["port_stability"] = _port_stability

    # Register API blueprint
    app.register_blueprint(api)

    # Initialize WebSocket support
    sock = Sock(app)
    register_terminal_routes(sock)

    def _auth_enabled():
        return bool(
            os.environ.get("MESHCORE_PASSWORD_HASH") or os.environ.get("MESHCORE_PASSWORD")
        )

    def _is_authenticated():
        return session.get("authenticated", False)

    @app.before_request
    def require_auth():
        # Always allow static files and login/logout
        if request.endpoint in ("login", "logout", "static", "auth_nonce"):
            return None

        # No password configured — everything is accessible
        if not _auth_enabled():
            return None

        # GET requests to the dashboard and read-only API are always public
        if request.method == "GET":
            return None

        # All write operations require authentication when a password is set
        if not _is_authenticated():
            if request.path.startswith("/api/") or request.path.startswith("/ws/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login"))

        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            ip = _client_ip()

            # Check fail2ban lockout
            if _is_locked_out(ip):
                remaining = config.LOGIN_LOCKOUT_SECS
                with _login_lock:
                    attempts = _login_attempts.get(ip, [])
                    if attempts:
                        elapsed = time.time() - attempts[-1]
                        remaining = max(1, int(config.LOGIN_LOCKOUT_SECS - elapsed))
                error = f"Too many failed attempts. Try again in {remaining}s."
                logger.warning("Locked out login attempt from %s", ip)
                return render_template("login.html", error=error)

            submitted = request.form.get("password", "")
            pw_hash   = os.environ.get("MESHCORE_PASSWORD_HASH", "")
            pw_plain  = os.environ.get("MESHCORE_PASSWORD", "")
            if pw_hash:
                ok = _bc.checkpw(submitted.encode(), pw_hash.encode())
            elif pw_plain:
                ok = _secrets.compare_digest(submitted, pw_plain)
            else:
                ok = False
            if ok:
                _clear_attempts(ip)
                session["authenticated"] = True
                return redirect(url_for("index"))
            _record_failed_attempt(ip)
            remaining_attempts = config.LOGIN_MAX_ATTEMPTS - len(_login_attempts.get(ip, []))
            if remaining_attempts > 0:
                error = f"Invalid password ({remaining_attempts} attempts remaining)"
            else:
                error = f"Too many failed attempts. Locked out for {config.LOGIN_LOCKOUT_SECS}s."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # Root route serves dashboard — always accessible
    @app.route("/")
    def index():
        return render_template(
            "index.html",
            auth_enabled=_auth_enabled(),
            is_authenticated=_is_authenticated(),
        )

    # Start collector
    poller = StatsPoller()
    app.config["poller"] = poller
    poller.start()

    # Start sensor poller
    sensor_poller = None
    if config.SENSOR_POLL_ENABLED:
        sensor_poller = SensorPoller()
        app.config["sensor_poller"] = sensor_poller
        sensor_poller.start()

    def shutdown_handler(signum, frame):
        logger.info("Shutting down collector...")
        poller.stop()
        if sensor_poller:
            sensor_poller.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        use_reloader=False,
    )

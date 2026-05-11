import logging
import time

import config

logger = logging.getLogger(__name__)

# Try RPi.GPIO first (legacy), then lgpio (modern Pi OS Bookworm+)
_backend = None

try:
    import RPi.GPIO as _rpigpio
    _backend = "rpigpio"
except ImportError:
    pass

if _backend is None:
    try:
        import lgpio as _lgpio
        _backend = "lgpio"
    except ImportError:
        pass


class _RpiGpioBackend:
    """Backend using RPi.GPIO (legacy Pi OS)."""

    def pulse(self, pin, sequences):
        _rpigpio.setmode(_rpigpio.BCM)
        _rpigpio.setup(pin, _rpigpio.OUT)
        _rpigpio.output(pin, _rpigpio.HIGH)
        try:
            for level, duration in sequences:
                _rpigpio.output(pin, level)
                time.sleep(duration)
        finally:
            _rpigpio.cleanup()

    @staticmethod
    def LOW():
        return _rpigpio.LOW

    @staticmethod
    def HIGH():
        return _rpigpio.HIGH


class _LgpioBackend:
    """Backend using lgpio (Pi OS Bookworm+)."""

    def pulse(self, pin, sequences):
        h = _lgpio.gpiochip_open(0)
        try:
            _lgpio.gpio_claim_output(h, pin, 1)  # start HIGH
            for level, duration in sequences:
                _lgpio.gpio_write(h, pin, level)
                time.sleep(duration)
        finally:
            _lgpio.gpiochip_close(h)

    @staticmethod
    def LOW():
        return 0

    @staticmethod
    def HIGH():
        return 1


def _get_backend():
    if _backend == "rpigpio":
        return _RpiGpioBackend()
    elif _backend == "lgpio":
        return _LgpioBackend()
    raise RuntimeError(
        "No GPIO library available. Install lgpio (pip install lgpio) "
        "or RPi.GPIO."
    )


def reset_radio(pin: int | None = None):
    """Pulse reset LOW for 0.5s — normal hard reset.

    If pin is None, falls back to config.RADIO_RESET_GPIO_PIN (radio A default).
    """
    be = _get_backend()
    actual_pin = pin if pin is not None else config.RADIO_RESET_GPIO_PIN
    be.pulse(actual_pin, [
        (be.LOW(), 0.5),
        (be.HIGH(), 0),
    ])
    logger.info("Radio reset via GPIO %d", actual_pin)


def bootloader_mode(pin: int | None = None):
    """Double-pulse reset for DFU/bootloader entry.

    If pin is None, falls back to config.RADIO_RESET_GPIO_PIN (radio A default).
    """
    be = _get_backend()
    actual_pin = pin if pin is not None else config.RADIO_RESET_GPIO_PIN
    be.pulse(actual_pin, [
        (be.LOW(), 0.1),
        (be.HIGH(), 0.2),
        (be.LOW(), 0.1),
        (be.HIGH(), 0),
    ])
    logger.info("Radio entered bootloader mode via GPIO %d", actual_pin)

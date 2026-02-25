import logging
import time

import config

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False


def _setup():
    pin = config.RADIO_RESET_GPIO_PIN
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)
    return pin


def reset_radio():
    """Pulse reset LOW for 0.5s — normal hard reset."""
    if not HAS_GPIO:
        raise RuntimeError("RPi.GPIO not available")
    pin = _setup()
    try:
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.5)
        GPIO.output(pin, GPIO.HIGH)
    finally:
        GPIO.cleanup()
    logger.info("Radio reset via GPIO %d", pin)


def bootloader_mode():
    """Double-pulse reset for DFU/bootloader entry."""
    if not HAS_GPIO:
        raise RuntimeError("RPi.GPIO not available")
    pin = _setup()
    try:
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.2)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(pin, GPIO.HIGH)
    finally:
        GPIO.cleanup()
    logger.info("Radio entered bootloader mode via GPIO %d", pin)

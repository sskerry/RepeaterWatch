from __future__ import annotations

import logging
import math
import threading
import time

import config
from database import models
from collector.sensors import ina3221_sensor, bme280_sensor, lis2dw12_sensor
from collector.sensors.as3935_sensor import AS3935

logger = logging.getLogger(__name__)

ACCEL_POLL_SECS = 5


class SensorPoller:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._as3935 = AS3935(irq_gpio=config.AS3935_IRQ_GPIO)
        self._sensor_status: dict[str, dict] = {
            "ina3221": {"ok": False, "last_error": None},
            "bme280": {"ok": False, "last_error": None},
            "lis2dw12": {"ok": False, "last_error": None},
            "as3935": {"ok": False, "last_error": None},
        }

    @property
    def status(self) -> dict:
        return {
            "running": self._thread is not None and self._thread.is_alive(),
            "sensors": dict(self._sensor_status),
        }

    def start(self):
        self._stop_event.clear()
        self._as3935.init()
        self._sensor_status["as3935"]["ok"] = self._as3935.available

        # Log sensor library availability at startup
        self._sensor_status["ina3221"]["ok"] = ina3221_sensor.HAS_INA3221
        self._sensor_status["bme280"]["ok"] = bme280_sensor.HAS_BME280
        self._sensor_status["lis2dw12"]["ok"] = lis2dw12_sensor.HAS_LIS2DW12

        available = []
        missing = []
        for name, mod in [("ina3221", ina3221_sensor), ("bme280", bme280_sensor),
                          ("lis2dw12", lis2dw12_sensor)]:
            flag = getattr(mod, "HAS_" + name.upper(), False)
            (available if flag else missing).append(name)
        if self._as3935.available:
            available.append("as3935")
        else:
            missing.append("as3935")

        logger.info("SensorPoller starting — available: [%s], missing: [%s]",
                     ", ".join(available) or "none",
                     ", ".join(missing) or "none")

        self._thread = threading.Thread(target=self._run, daemon=True, name="sensor-poller")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._as3935.cleanup()

    def _run(self):
        logger.info("SensorPoller thread started")
        try:
            self._run_loop()
        except Exception:
            logger.exception("SensorPoller thread crashed")

    def _run_loop(self):
        # Accumulation buffers for readings within a 5-min window
        accel_buf: list[dict] = []
        power_buf: list[dict] = []

        while not self._stop_event.is_set():
            current_ts = models.aligned_ts()
            next_boundary = current_ts + 300
            wait_secs = next_boundary - time.time()
            logger.info("Waiting %.0fs for next 5-min boundary (ts=%d)", wait_secs, next_boundary)

            # Inner loop: poll sensors every 5s until next 5-min boundary
            while not self._stop_event.is_set():
                now = time.time()
                if now >= next_boundary:
                    break

                # Poll INA3221
                try:
                    reading = ina3221_sensor.read()
                    if reading is not None:
                        power_buf.append(reading)
                        self._sensor_status["ina3221"]["ok"] = True
                except Exception as e:
                    self._sensor_status["ina3221"]["last_error"] = str(e)

                # Poll accelerometer
                try:
                    reading = lis2dw12_sensor.read()
                    if reading is not None:
                        accel_buf.append(reading)
                        self._sensor_status["lis2dw12"]["ok"] = True
                except Exception as e:
                    self._sensor_status["lis2dw12"]["last_error"] = str(e)

                # Drain and store AS3935 events immediately
                self._store_lightning_events()

                # Wait for next poll or boundary
                wait = min(ACCEL_POLL_SECS, next_boundary - time.time())
                if wait > 0:
                    self._stop_event.wait(wait)

            if self._stop_event.is_set():
                break

            # 5-minute boundary reached — aggregate and store
            ts = models.aligned_ts()
            logger.info("Sensor poll cycle at ts=%d (power samples=%d, accel samples=%d)",
                        ts, len(power_buf), len(accel_buf))

            # INA3221 — average over window
            if power_buf:
                try:
                    n = len(power_buf)
                    ch0_v = sum(r["ch0_voltage"] for r in power_buf) / n
                    ch0_i = sum(r["ch0_current"] for r in power_buf) / n
                    ch1_v = sum(r["ch1_voltage"] for r in power_buf) / n
                    ch1_i = sum(r["ch1_current"] for r in power_buf) / n
                    models.insert_sensor_power(
                        ts,
                        ch0_v=round(ch0_v, 4),
                        ch0_i=round(ch0_i, 2),
                        ch0_p=round(ch0_v * ch0_i, 2),
                        ch1_v=round(ch1_v, 4),
                        ch1_i=round(ch1_i, 2),
                        ch1_p=round(ch1_v * ch1_i, 2),
                    )
                    logger.info("INA3221: %d samples, ch0=%.3fV/%.1fmA ch1=%.3fV/%.1fmA",
                                n, ch0_v, ch0_i, ch1_v, ch1_i)
                except Exception:
                    logger.exception("INA3221 aggregation error")
                power_buf = []
            else:
                self._sensor_status["ina3221"]["ok"] = False

            # BME280 — latest reading
            try:
                data = bme280_sensor.read()
                if data is not None:
                    models.insert_sensor_env(
                        ts,
                        temperature=data["temperature"],
                        humidity=data["humidity"],
                        pressure=data["pressure"],
                    )
                    self._sensor_status["bme280"]["ok"] = True
                    logger.info("BME280: %.1f°C / %.1f%% / %.1f hPa",
                                data["temperature"], data["humidity"], data["pressure"])
                else:
                    self._sensor_status["bme280"]["ok"] = False
            except Exception as e:
                self._sensor_status["bme280"]["last_error"] = str(e)
                logger.exception("BME280 poll error")

            # Accelerometer — aggregate buffer
            if accel_buf:
                try:
                    mags = [r["magnitude"] for r in accel_buf]
                    tilts = [r["tilt"] for r in accel_buf]
                    xs = [r["x"] for r in accel_buf]
                    ys = [r["y"] for r in accel_buf]
                    zs = [r["z"] for r in accel_buf]
                    n = len(accel_buf)
                    models.insert_sensor_accel(
                        ts,
                        vib_avg=round(sum(mags) / n, 4),
                        vib_peak=round(max(mags), 4),
                        tilt_avg=round(sum(tilts) / n, 2),
                        x_avg=round(sum(xs) / n, 4),
                        y_avg=round(sum(ys) / n, 4),
                        z_avg=round(sum(zs) / n, 4),
                    )
                    logger.info("LIS2DW12: %d samples, avg_mag=%.4f, peak=%.4f",
                                n, sum(mags) / n, max(mags))
                except Exception:
                    logger.exception("Accelerometer aggregation error")
                accel_buf = []

            # Final drain of lightning events
            self._store_lightning_events()

    def _store_lightning_events(self):
        events = self._as3935.drain_events()
        for evt in events:
            try:
                models.insert_lightning_event(
                    ts=evt["ts"],
                    event_type=evt["event_type"],
                    distance_km=evt["distance_km"],
                    energy=evt["energy"],
                )
            except Exception:
                logger.exception("Failed to store lightning event")

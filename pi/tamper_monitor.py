"""Background daemon thread: RTC-driven TFT clock + continuous tamper watch.

Runs alongside the button-triggered access_control loop, not instead of it --
access_control.py starts this once at boot via start(). Tamper detection
(accelerometer) and the access-request flow (fingerprint+face) are
independent concerns and shouldn't block each other.
"""
import threading
import time
from datetime import datetime, timezone

import config
import gpio_io
import rtc_clock
import tamper_sensor
import tft_display
import sms_alert
import backend_client

_TAMPER_COOLDOWN_S = 5  # minimum gap between repeated tamper alerts, so a
                        # single knock doesn't spam SMS/backend in a loop


def _now_iso():
    # Same UTC/millisecond/"Z" format access_control.py uses -- required for
    # the backend's hash-verification to line up (see access_control.py).
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_lid_state():
    if config.LID_SWITCH_PIN is None:
        return "unknown"
    try:
        import pigpio
        pi = pigpio.pi()
        return "closed" if pi.read(config.LID_SWITCH_PIN) else "open"
    except Exception:
        return "unknown"


def _post_tamper_event(vibration_g):
    payload_sensor_data = {
        "vibration": True,
        "accel_delta": vibration_g,
        "lid_switch": _read_lid_state(),
    }
    backend_client.log_event(
        status="TAMPER_ALERT",
        tamper=True,
        device_ts=_now_iso(),
        sensor_data=payload_sensor_data,
        lat=config.DEFAULT_LAT,
        lng=config.DEFAULT_LNG,
    )


def _loop():
    last_tamper_at = 0.0
    gpio_io.set_secure_idle()

    while True:
        now = rtc_clock.now()
        vibration_g = tamper_sensor.read_delta_g()
        tampered = tamper_sensor.is_tamper(vibration_g)

        if tampered:
            tft_display.update(now, "TAMPER ALERT!")
            if time.time() - last_tamper_at > _TAMPER_COOLDOWN_S:
                last_tamper_at = time.time()
                print(f"[tamper_monitor] TAMPER detected (accel delta {vibration_g}g)")
                gpio_io.alert_start()
                _post_tamper_event(vibration_g)
                sms_alert.send_tamper_sms(config.DEFAULT_LAT, config.DEFAULT_LNG)
        else:
            tft_display.update(now, "SECURE")
            if time.time() - last_tamper_at > _TAMPER_COOLDOWN_S:
                gpio_io.alert_stop()  # no-op if already idle; clears a resolved alert

        time.sleep(config.TAMPER_POLL_INTERVAL_S)


def start():
    """Starts the monitor loop on a daemon thread -- dies with the process,
    never blocks shutdown."""
    t = threading.Thread(target=_loop, daemon=True, name="tamper_monitor")
    t.start()
    return t

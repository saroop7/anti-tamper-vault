"""Background daemon thread: polls the backend for enrollment requests the
frontend queued, and runs the fingerprint+face capture automatically when
one arrives -- no terminal, no typing on the Pi.

Runs alongside access_control's normal access-check loop; sensor_lock.py
keeps the two from ever touching the R307 UART at the same instant.
"""
import threading
import time

import requests
import serial
import adafruit_fingerprint

import config
import enrollment_logic as logic
import tft_display
import rtc_clock
from sensor_lock import fingerprint_lock

_API_HEADERS = {"Content-Type": "application/json", "x-api-key": config.INGEST_API_KEY}


def _fetch_pending():
    try:
        res = requests.get(
            f"{config.BACKEND_URL}/enrollment-requests/pending",
            headers=_API_HEADERS, timeout=config.BACKEND_TIMEOUT_S,
        )
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        print(f"[enrollment_worker] poll failed: {e}")
        return None


def _report_status(request_id, status, error=None, enrollment_id=None):
    try:
        requests.post(
            f"{config.BACKEND_URL}/enrollment-requests/{request_id}/status",
            json={"status": status, "error": error, "enrollment_id": enrollment_id},
            headers=_API_HEADERS, timeout=config.BACKEND_TIMEOUT_S,
        )
    except requests.RequestException as e:
        print(f"[enrollment_worker] failed to report status: {e}")


def _make_should_cancel(request_id):
    """A should_cancel() closure passed into the capture loops. Only hits
    the network at most once/second (those loops iterate much faster than
    that) and caches a positive result so one confirmed cancel sticks even
    if a later check has a network hiccup."""
    state = {"last_check": 0.0, "cancelled": False}

    def should_cancel():
        if state["cancelled"]:
            return True
        now = time.time()
        if now - state["last_check"] < 1.0:
            return False
        state["last_check"] = now
        try:
            res = requests.get(
                f"{config.BACKEND_URL}/enrollment-requests/{request_id}/status",
                headers=_API_HEADERS, timeout=2,
            )
            if res.ok and res.json().get("status") == "cancelled":
                state["cancelled"] = True
        except requests.RequestException:
            pass  # transient network hiccup -- don't cancel just because one check failed
        return state["cancelled"]

    return should_cancel


def _run_enrollment(request):
    name = request["name"]
    request_id = request["id"]
    print(f"[enrollment_worker] starting enrollment for '{name}' (request #{request_id})")
    _report_status(request_id, "in_progress")
    tft_display.update(rtc_clock.now(), "ENROLLING...")
    should_cancel = _make_should_cancel(request_id)

    with fingerprint_lock:
        try:
            uart = serial.Serial(config.FINGERPRINT_PORT, baudrate=config.FINGERPRINT_BAUD, timeout=1)
            finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)
            if finger.read_sysparam() != adafruit_fingerprint.OK:
                raise RuntimeError("R307 not responding")

            slot = logic.get_next_slot()
            if not slot:
                raise RuntimeError("fingerprint memory full")

            if not logic.enroll_fingerprint(finger, slot, should_cancel=should_cancel):
                raise RuntimeError("fingerprint enrollment failed")

            face_b64 = logic.capture_clear_face(should_cancel=should_cancel)
            logic.save_local(name, slot, face_b64)

            result = logic.submit_enrollment(
                config.BACKEND_URL, config.INGEST_API_KEY, config.DEVICE_ID, name, slot, face_b64
            )
            _report_status(request_id, "done", enrollment_id=result.get("id"))
            print(f"[enrollment_worker] '{name}' enrolled -> slot {slot}, enrollment #{result.get('id')}")
            tft_display.update(rtc_clock.now(), "ENROLLED OK")
        except logic.EnrollmentCancelled:
            # Status is already "cancelled" server-side (that's how
            # should_cancel() found out) -- don't overwrite it via
            # _report_status, just stop.
            print(f"[enrollment_worker] enrollment for '{name}' was cancelled from the frontend")
            tft_display.update(rtc_clock.now(), "ENROLL CANCELLED")
        except Exception as e:
            print(f"[enrollment_worker] enrollment failed: {e}")
            _report_status(request_id, "failed", error=str(e))
            tft_display.update(rtc_clock.now(), "ENROLL FAILED")

    time.sleep(2)  # let the result show on the TFT briefly before the tamper monitor overwrites it


def _loop():
    while True:
        request = _fetch_pending()
        if request:
            _run_enrollment(request)
        time.sleep(config.ENROLLMENT_POLL_INTERVAL_S)


def start():
    t = threading.Thread(target=_loop, daemon=True, name="enrollment_worker")
    t.start()
    return t

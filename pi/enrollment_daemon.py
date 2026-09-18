#!/usr/bin/env python3
"""
ANTI-TAMPER VAULT - STANDALONE ENROLLMENT DAEMON

Polls the backend for enrollment requests the frontend queued, and runs the
fingerprint + face capture automatically when one arrives.

Deliberately dependency-light and dotenv-free so it runs straight from
Thonny (or plain system Python, no venv) without needing swig/lgpio/pigpio/
Pillow/ST7735 -- this only needs pyserial, adafruit-circuitpython-fingerprint,
opencv-contrib-python, picamera2, and requests. Config is hardcoded below
instead of read from .env; edit the constants directly if anything changes.

This is the enrollment piece only -- it does NOT run the tamper/access
daemon (that's access_control.py, which does need the heavier hardware
libs for the servo/siren/RTC/TFT). Run this on its own whenever you just
want "frontend button -> Pi captures fingerprint+face" without the rest.
"""
import time

import requests
import serial
import adafruit_fingerprint

import enrollment_logic as logic

# ==========================================
# CONFIGURATION -- edit these directly, no .env needed
# ==========================================
BACKEND_URL = "http://saroops-macbook-air.tailb523e7.ts.net:3000"
INGEST_API_KEY = "124135a146b3e5b3a8743af03228b546f24bcec9749f74d7a6590e35edcaa90a"
DEVICE_ID = "vault-pi-01"
FINGERPRINT_PORT = "/dev/ttyUSB0"  # matches pi/.env -- change if your R307 is on a different port
FINGERPRINT_BAUD = 57600
POLL_INTERVAL_S = 3

_API_HEADERS = {"Content-Type": "application/json", "x-api-key": INGEST_API_KEY}


def _fetch_pending():
    try:
        res = requests.get(f"{BACKEND_URL}/enrollment-requests/pending", headers=_API_HEADERS, timeout=5)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        print(f"[enrollment_daemon] poll failed: {e}")
        return None


def _report_status(request_id, status, error=None, enrollment_id=None):
    try:
        requests.post(
            f"{BACKEND_URL}/enrollment-requests/{request_id}/status",
            json={"status": status, "error": error, "enrollment_id": enrollment_id},
            headers=_API_HEADERS, timeout=5,
        )
    except requests.RequestException as e:
        print(f"[enrollment_daemon] failed to report status: {e}")


def _make_should_cancel(request_id):
    state = {"last_check": 0.0, "cancelled": False}

    def should_cancel():
        if state["cancelled"]:
            return True
        now = time.time()
        if now - state["last_check"] < 1.0:
            return False
        state["last_check"] = now
        try:
            res = requests.get(f"{BACKEND_URL}/enrollment-requests/{request_id}/status", headers=_API_HEADERS, timeout=2)
            if res.ok and res.json().get("status") == "cancelled":
                state["cancelled"] = True
        except requests.RequestException:
            pass
        return state["cancelled"]

    return should_cancel


def _run_enrollment(request):
    name = request["name"]
    request_id = request["id"]
    print(f"[enrollment_daemon] starting enrollment for '{name}' (request #{request_id})")
    _report_status(request_id, "in_progress")
    should_cancel = _make_should_cancel(request_id)

    try:
        print("[INIT] Connecting to R307 Fingerprint Scanner...")
        uart = serial.Serial(FINGERPRINT_PORT, baudrate=FINGERPRINT_BAUD, timeout=1)
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

        result = logic.submit_enrollment(BACKEND_URL, INGEST_API_KEY, DEVICE_ID, name, slot, face_b64)
        _report_status(request_id, "done", enrollment_id=result.get("id"))
        print(f"[enrollment_daemon] '{name}' enrolled -> slot {slot}, enrollment #{result.get('id')}")
    except logic.EnrollmentCancelled:
        print(f"[enrollment_daemon] enrollment for '{name}' was cancelled from the frontend")
    except Exception as e:
        print(f"[enrollment_daemon] enrollment failed: {e}")
        _report_status(request_id, "failed", error=str(e))


if __name__ == "__main__":
    print(f"[enrollment_daemon] polling {BACKEND_URL}/enrollment-requests/pending every {POLL_INTERVAL_S}s")
    print("[enrollment_daemon] Ctrl+C to stop")
    while True:
        request = _fetch_pending()
        if request:
            _run_enrollment(request)
        time.sleep(POLL_INTERVAL_S)

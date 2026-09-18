#!/usr/bin/env python3
"""
ANTI-TAMPER VAULT ECS - USER ENROLLMENT & BACKEND SYNC
Captures fingerprint and face data, stores locally, and POSTs to server.
"""

import time
import json
import serial
import requests
import cv2
import base64
from datetime import datetime, timezone
import adafruit_fingerprint

# ==========================================
# 1. API & BACKEND CONFIGURATION
# ==========================================
BACKEND_URL = "http://saroops-macbook-air.tailb523e7.ts.net:3000"
API_URL = f"{BACKEND_URL}/events"
USERS_URL = f"{BACKEND_URL}/users/register"
API_HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": "124135a146b3e5b3a8743af03228b546f24bcec9749f74d7a6590e35edcaa90a"
}
DEVICE_ID = "vault-001"
LOCAL_DB = "authorized_users.json"

# ==========================================
# 2. HARDWARE INITIALIZATION
# ==========================================
print("[INIT] Connecting to R307 Fingerprint Scanner...")
try:
    # NOTE: /dev/serial0 on a Pi 3B/3B+/4 maps to the mini-UART by default,
    # whose baud rate drifts with CPU core clock -- this is the classic cause
    # of "get_image() OK, image_2_tz() fails" since larger transfers are more
    # exposed to clock jitter than small handshake commands. If the error
    # code below keeps appearing randomly on a clean scan, switch to
    # /dev/ttyAMA0 (after `dtoverlay=disable-bt` in config.txt + disabling
    # hciuart) or, more reliably, a USB-to-TTL adapter on /dev/ttyUSB0.
    uart_r307 = serial.Serial("/dev/serial0", baudrate=57600, timeout=1)
    finger = adafruit_fingerprint.Adafruit_Fingerprint(uart_r307)
    if finger.read_sysparam() == adafruit_fingerprint.OK:
        print(f"[SUCCESS] R307 Online. Stored templates: {finger.template_count}")
    else:
        raise RuntimeError("R307 not responding to system parameters query.")
except Exception as e:
    print(f"[ERROR] Fingerprint initialization failed: {e}")
    exit(1)

# ==========================================
# 3. ENROLLMENT & CAPTURE FUNCTIONS
# ==========================================
def enroll_fingerprint(slot_id):
    """Guides the user through a 2-step physical fingerprint scan for the R307."""
    for step in range(1, 3):
        if step == 1:
            print(f"\n[FINGERPRINT] Place finger on scanner for Slot #{slot_id}...")
        else:
            print("[FINGERPRINT] Place the SAME finger again to verify...")

        while True:
            img = finger.get_image()
            if img == adafruit_fingerprint.OK:
                print(" -> Image captured successfully.")
                break
            elif img == adafruit_fingerprint.NOFINGER:
                pass
            else:
                print(" -> Scan error, try again.")

        tz_result = finger.image_2_tz(step)
        if tz_result != adafruit_fingerprint.OK:
            print(f" -> Processing error (code: {tz_result}). Aborting.")
            return False

        if step == 1:
            print(" -> Remove your finger from the sensor.")
            time.sleep(2)
            while finger.get_image() != adafruit_fingerprint.NOFINGER:
                pass

    print("[FINGERPRINT] Creating biometric model match...")
    if finger.create_model() != adafruit_fingerprint.OK:
        print(" -> Fingerprints did not match. Aborting.")
        return False

    print(f"[FINGERPRINT] Storing model into hardware Slot #{slot_id}...")
    if finger.store_model(slot_id) == adafruit_fingerprint.OK:
        print(f"[SUCCESS] Fingerprint saved to R307 Slot #{slot_id}!")
        return True

    print("-> Failed to store fingerprint model.")
    return False

def capture_face():
    """Captures a frame via the Pi camera and encodes it to base64.

    Uses picamera2 (the libcamera-based API), not cv2.VideoCapture(0) --
    a CSI ribbon camera (like the Pi Camera rev 1.3) isn't a V4L2 webcam
    device, so OpenCV's own capture almost always silently fails on it
    (cap.read() returns ret=False) even though the camera itself is fine.
    """
    print("\n[CAMERA] Look directly at the Pi Camera. Capturing in 3 seconds...")
    time.sleep(3)

    try:
        from picamera2 import Picamera2

        picam2 = Picamera2()
        cfg = picam2.create_still_configuration(main={"size": (320, 240), "format": "RGB888"})
        picam2.configure(cfg)
        picam2.start()
        time.sleep(0.5)  # let auto-exposure settle
        frame_rgb = picam2.capture_array()
        picam2.stop()
        picam2.close()

        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode('.jpg', frame_bgr)
        b64_string = base64.b64encode(buffer).decode('utf-8')
        print("[SUCCESS] Face frame captured.")
        return b64_string
    except Exception as e:
        print(f"[ERROR] Camera failed to capture frame: {e}")
        return None

# ==========================================
# 4. MAIN EXECUTION FLOW
# ==========================================
if __name__ == "__main__":
    print("\n==================================================")
    print(" ANTI-TAMPER VAULT ECS - USER ENROLLMENT SUITE")
    print("==================================================")

    username = input("Enter new authorized username: ").strip()
    email = input("Enter email for backend account: ").strip()
    password = input("Enter password for backend account (min 8 chars): ").strip()
    slot = int(input("Enter fingerprint slot ID to use (1-127): "))

    # Step A: Perform Biometric Hardware Enrollment
    if enroll_fingerprint(slot):

        # Step B: Capture Facial Data via OpenCV / Pi Camera
        face_b64 = capture_face()

        # Step C: Save Record Locally
        user_record = {
            "username": username,
            "r307_slot": slot,
            "enrolled_at": int(time.time())
        }

        try:
            with open(LOCAL_DB, "r") as f:
                db = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            db = {"authorized_users": []}

        db["authorized_users"].append(user_record)
        with open(LOCAL_DB, "w") as f:
            json.dump(db, f, indent=4)

        print(f"\n[LOCAL DB] Saved user '{username}' to {LOCAL_DB}")

        # Step D: Construct and Transmit Payload to Backend API
        print(f"\n[API] Transmitting user data to backend: {API_URL}...")

        # Must be UTC, millisecond precision, "Z" suffix -- matches what the
        # backend's hash-verification does internally (Postgres/JS Date
        # round-trip), otherwise this event permanently fails /verify even
        # though nothing was tampered.
        device_ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

        api_payload = {
            "device_id": DEVICE_ID,
            "device_ts": device_ts,
            "status": "user_registered",
            "tamper": False,
            "sensor_data": {
                "name": username,
                "fingerprint_slot": slot,
                "face_id": face_b64 if face_b64 else "no_image_captured",
                "firmware_ver": "1.2.0-enroll",
            },
            # no "lat"/"lng" keys -- omit rather than send null, the backend
            # rejects null explicitly ("lat must be a number")
        }

        try:
            response = requests.post(API_URL, json=api_payload, headers=API_HEADERS, timeout=5)
            print(f"[API RESPONSE] Status Code: {response.status_code}")
            print(f"[API RESPONSE] Message Body: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"[API ERROR] Failed to connect to server at {API_URL}. Saved locally instead.")
            print(f"Details: {e}")

        # Step E: Create a real login-capable backend account for this user
        # (separate from the /events audit trail above -- this is the actual
        # users table, so they can log in with email/password later).
        print(f"\n[API] Registering backend account for '{email}'...")
        try:
            reg_response = requests.post(
                USERS_URL,
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            print(f"[API RESPONSE] Status Code: {reg_response.status_code}")
            print(f"[API RESPONSE] Message Body: {reg_response.text}")
        except requests.exceptions.RequestException as e:
            print(f"[API ERROR] Failed to reach {USERS_URL} to register the account.")
            print(f"Details: {e}")

    else:
        print("\n[FAILED] Enrollment sequence aborted due to hardware error.")

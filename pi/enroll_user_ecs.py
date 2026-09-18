#!/usr/bin/env python3
"""
ANTI-TAMPER VAULT ECS - AUTOMATED USER ENROLLMENT

Captures fingerprint + face, auto-assigns the next free fingerprint slot,
saves locally, and syncs the enrollment to the backend ledger.
"""
import time
import json
import serial
import requests
import cv2
import base64
import adafruit_fingerprint

# ==========================================
# 1. API & BACKEND CONFIGURATION
# ==========================================
# Tailscale MagicDNS hostname -- stable regardless of which WiFi either
# device is on, no more updating this when the Mac reconnects.
BACKEND_URL = "http://saroops-macbook-air.tailb523e7.ts.net:3000"
API_URL = f"{BACKEND_URL}/enrollments"
API_HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": "124135a146b3e5b3a8743af03228b546f24bcec9749f74d7a6590e35edcaa90a"
}
DEVICE_ID = "vault-001"
LOCAL_DB = "enrollments.json"

# ==========================================
# 2. HARDWARE INITIALIZATION
# ==========================================
print("[INIT] Connecting to R307 Fingerprint Scanner...")
uart_r307 = serial.Serial("/dev/serial0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart_r307)
if finger.read_sysparam() == adafruit_fingerprint.OK:
    print(f"[SUCCESS] R307 Online. Stored templates: {finger.template_count}")
else:
    print("[ERROR] R307 not responding to system parameters query.")
    exit(1)

# ==========================================
# 3. SLOT ASSIGNMENT & CAPTURE FUNCTIONS
# ==========================================
def get_next_slot():
    """Automatically finds the next available fingerprint slot (1-127)."""
    try:
        with open(LOCAL_DB, "r") as f:
            db = json.load(f)
            used_slots = [u["fingerprint_slot"] for u in db.get("enrollments", [])]
    except (FileNotFoundError, json.JSONDecodeError):
        used_slots = []

    for slot in range(1, 128):
        if slot not in used_slots:
            return slot
    return None

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

        if finger.image_2_tz(step) != adafruit_fingerprint.OK:
            print(" -> Processing error. Aborting.")
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

    print(" -> Failed to store fingerprint model.")
    return False

def capture_clear_face():
    """Gives a 10-second window and keeps the sharpest of many frames.

    Uses picamera2 (the libcamera-based API), not cv2.VideoCapture(0) --
    a CSI ribbon camera (like the Pi Camera rev 1.3) isn't a V4L2 webcam
    device, so OpenCV's own capture almost always silently fails on it
    (cap.read() returns ret=False) even though the camera itself is fine.
    """
    from picamera2 import Picamera2

    picam2 = Picamera2()
    cfg = picam2.create_still_configuration(main={"size": (320, 240), "format": "RGB888"})
    picam2.configure(cfg)
    picam2.start()
    time.sleep(0.5)  # let auto-exposure settle

    print("\n[CAMERA] Position your face. Capturing the clearest frame over 10 seconds...")
    best_frame = None
    max_sharpness = 0.0
    start_time = time.time()

    while time.time() - start_time < 10:
        frame_rgb = picam2.capture_array()
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        if sharpness > max_sharpness:
            max_sharpness = sharpness
            best_frame = frame_bgr
        time.sleep(0.2)

    picam2.stop()
    picam2.close()

    if best_frame is not None:
        _, buffer = cv2.imencode('.jpg', best_frame)
        print(f"[SUCCESS] Face captured (sharpness score: {max_sharpness:.1f}).")
        return base64.b64encode(buffer).decode('utf-8')

    print("[ERROR] No usable face frame captured.")
    return None

# ==========================================
# 4. MAIN EXECUTION FLOW
# ==========================================
if __name__ == "__main__":
    print("\n==================================================")
    print(" ANTI-TAMPER VAULT ECS - AUTOMATED USER REGISTRATION")
    print("==================================================")

    username = input("Enter user name: ").strip()
    slot = get_next_slot()
    if not slot:
        print("[ERROR] Fingerprint memory full!")
        exit(1)

    print(f"Assigned Fingerprint Slot: {slot}")
    if enroll_fingerprint(slot):
        face_b64 = capture_clear_face()

        # Save locally
        user_record = {"name": username, "fingerprint_slot": slot, "face_id": face_b64}
        try:
            with open(LOCAL_DB, "r") as f:
                db = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            db = {}
        # .setdefault, not db["enrollments"], so a stale file from an older
        # script version (different top-level key) can't KeyError here --
        # it just gets an "enrollments" list added alongside whatever else is in it.
        db.setdefault("enrollments", []).append(user_record)
        with open(LOCAL_DB, "w") as f:
            json.dump(db, f, indent=4)
        print(f"\n[LOCAL DB] Saved user '{username}' to {LOCAL_DB}")

        payload = {
            "device_id": DEVICE_ID,
            "name": username,
            "fingerprint_slot": slot,
            "face_id": face_b64 if face_b64 else "no_image_captured",
            "firmware_ver": "1.2.0-enroll",
        }

        print(f"\n[API] Transmitting user data to backend: {API_URL}...")
        try:
            res = requests.post(API_URL, json=payload, headers=API_HEADERS, timeout=5)
            print(f"[API RESPONSE] Status Code: {res.status_code}")
            print(f"[API RESPONSE] Message Body: {res.text}")
        except requests.exceptions.RequestException as e:
            print(f"[API ERROR] Failed to connect to server at {API_URL}. Saved locally instead.")
            print(f"Details: {e}")
    else:
        print("\n[FAILED] Enrollment sequence aborted due to hardware error.")

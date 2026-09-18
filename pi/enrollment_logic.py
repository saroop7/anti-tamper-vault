"""Shared fingerprint + face enrollment steps.

Used by both enroll_user_ecs.py (run manually, prompts on the terminal) and
enrollment_worker.py (runs inside the daemon, triggered by a request queued
from the frontend) -- one implementation, two ways to kick it off.
"""
import time
import json
import base64

import adafruit_fingerprint
import cv2
import requests

LOCAL_DB = "enrollments.json"


class EnrollmentCancelled(Exception):
    """Raised mid-capture when should_cancel() reports the frontend hit stop."""


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


def enroll_fingerprint(finger, slot_id, should_cancel=lambda: False):
    """Guides through a 2-step physical fingerprint scan on an already-open
    `finger` (adafruit_fingerprint.Adafruit_Fingerprint instance).

    should_cancel() is polled on every loop iteration (not just before
    starting) so a "stop" click actually interrupts a scan that's sitting
    there waiting for a finger, not just one that hasn't started yet.
    """
    for step in range(1, 3):
        if step == 1:
            print(f"\n[FINGERPRINT] Place finger on scanner for Slot #{slot_id}...")
        else:
            print("[FINGERPRINT] Place the SAME finger again to verify...")

        while True:
            if should_cancel():
                raise EnrollmentCancelled()
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
                if should_cancel():
                    raise EnrollmentCancelled()

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


MIN_FRAME_BRIGHTNESS = 15.0  # mean gray-level below this reads as blank/lens-covered, not a face


def capture_clear_face(should_cancel=lambda: False):
    """Gives a 10-second window and keeps the sharpest of many frames.

    Uses picamera2 (the libcamera-based API), not cv2.VideoCapture(0) --
    a CSI ribbon camera (like the Pi Camera rev 1.3) isn't a V4L2 webcam
    device, so OpenCV's own capture almost always silently fails on it
    (cap.read() returns ret=False) even though the camera itself is fine.

    Frames darker than MIN_FRAME_BRIGHTNESS are skipped before the sharpness
    check -- a near-black frame (lens cap on, no light, sensor still warming
    up) can score a 0.0 Laplacian variance and would otherwise never beat
    max_sharpness, silently starving best_frame for the whole 10s window.
    """
    from picamera2 import Picamera2

    picam2 = Picamera2()
    cfg = picam2.create_still_configuration(main={"size": (320, 240), "format": "RGB888"})
    picam2.configure(cfg)
    picam2.start()
    time.sleep(1.5)  # let auto-exposure settle -- 0.5s was too short on some CSI sensors

    print("\n[CAMERA] Position your face. Capturing the clearest frame over 10 seconds...")
    best_frame = None
    max_sharpness = 0.0
    dark_frames = 0
    total_frames = 0
    start_time = time.time()
    last_log = start_time

    while time.time() - start_time < 10:
        if should_cancel():
            picam2.stop()
            picam2.close()
            raise EnrollmentCancelled()
        frame_rgb = picam2.capture_array()
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        total_frames += 1

        brightness = gray.mean()
        if brightness < MIN_FRAME_BRIGHTNESS:
            dark_frames += 1
        else:
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            if sharpness > max_sharpness:
                max_sharpness = sharpness
                best_frame = frame_bgr

        now = time.time()
        if now - last_log >= 1.0:
            print(f"[CAMERA] t={now - start_time:.1f}s  brightness={brightness:.1f}  "
                  f"best_sharpness={max_sharpness:.1f}  dark_frames={dark_frames}/{total_frames}")
            last_log = now

        time.sleep(0.2)

    picam2.stop()
    picam2.close()

    if best_frame is not None:
        _, buffer = cv2.imencode('.jpg', best_frame)
        print(f"[SUCCESS] Face captured (sharpness score: {max_sharpness:.1f}).")
        return base64.b64encode(buffer).decode('utf-8')

    if dark_frames == total_frames and total_frames > 0:
        print(f"[ERROR] No usable face frame captured -- all {total_frames} frames were "
              f"below brightness {MIN_FRAME_BRIGHTNESS} (check lens cap / lighting / camera cable).")
    else:
        print(f"[ERROR] No usable face frame captured ({dark_frames}/{total_frames} dark, "
              f"best sharpness among the rest was {max_sharpness:.1f}).")
    return None


def save_local(name, slot, face_b64):
    user_record = {"name": name, "fingerprint_slot": slot, "face_id": face_b64}
    try:
        with open(LOCAL_DB, "r") as f:
            db = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        db = {}
    # .setdefault, not db["enrollments"], so a stale file from an older
    # script version (different top-level key) can't KeyError here.
    db.setdefault("enrollments", []).append(user_record)
    with open(LOCAL_DB, "w") as f:
        json.dump(db, f, indent=4)


def submit_enrollment(backend_url, api_key, device_id, name, slot, face_b64):
    """POSTs the completed enrollment to the backend. Returns the parsed
    JSON response on success, raises on network/HTTP failure."""
    payload = {
        "device_id": device_id,
        "name": name,
        "fingerprint_slot": slot,
        "face_id": face_b64 if face_b64 else "no_image_captured",
        "firmware_ver": "1.2.0-enroll",
    }
    res = requests.post(
        f"{backend_url}/enrollments", json=payload,
        headers={"Content-Type": "application/json", "x-api-key": api_key},
        timeout=10,
    )
    res.raise_for_status()
    return res.json()

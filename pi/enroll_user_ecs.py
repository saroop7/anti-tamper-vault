#!/usr/bin/env python3
"""
ANTI-TAMPER VAULT ECS - MANUAL USER ENROLLMENT (run directly on the Pi)

For triggering an enrollment from the frontend instead, see
enrollment_worker.py -- it runs the same steps automatically as part of
the access_control daemon, no terminal needed.
"""
import serial
import adafruit_fingerprint

import config
import enrollment_logic as logic

if __name__ == "__main__":
    print("\n==================================================")
    print(" ANTI-TAMPER VAULT ECS - AUTOMATED USER REGISTRATION")
    print("==================================================")

    print("[INIT] Connecting to R307 Fingerprint Scanner...")
    uart_r307 = serial.Serial("/dev/serial0", baudrate=57600, timeout=1)
    finger = adafruit_fingerprint.Adafruit_Fingerprint(uart_r307)
    if finger.read_sysparam() == adafruit_fingerprint.OK:
        print(f"[SUCCESS] R307 Online. Stored templates: {finger.template_count}")
    else:
        print("[ERROR] R307 not responding to system parameters query.")
        exit(1)

    username = input("Enter user name: ").strip()
    slot = logic.get_next_slot()
    if not slot:
        print("[ERROR] Fingerprint memory full!")
        exit(1)

    print(f"Assigned Fingerprint Slot: {slot}")
    if logic.enroll_fingerprint(finger, slot):
        face_b64 = logic.capture_clear_face()
        logic.save_local(username, slot, face_b64)
        print(f"\n[LOCAL DB] Saved user '{username}' to {logic.LOCAL_DB}")

        print(f"\n[API] Transmitting user data to backend: {config.BACKEND_URL}/enrollments...")
        try:
            result = logic.submit_enrollment(
                config.BACKEND_URL, config.INGEST_API_KEY, config.DEVICE_ID, username, slot, face_b64
            )
            print(f"[API SUCCESS] {result}")
        except Exception as e:
            print(f"[API ERROR] Failed to sync to server: {e}")
    else:
        print("\n[FAILED] Enrollment sequence aborted due to hardware error.")

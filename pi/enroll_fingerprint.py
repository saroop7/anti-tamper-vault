"""Run this once to enroll Mr Sarkar's fingerprint into the R307's onboard
flash at slot config.OWNER_FINGERPRINT_ID. Requires two scans of the same
finger (the sensor's own requirement, for a reliable template).

Usage: python3 enroll_fingerprint.py
"""
import time
import serial
import adafruit_fingerprint
import config


def get_fingerprint_image(prompt):
    input(prompt)
    print("Scanning...")
    while True:
        result = finger.get_image()
        if result == adafruit_fingerprint.OK:
            print("Image taken.")
            return
        elif result == adafruit_fingerprint.NOFINGER:
            time.sleep(0.1)
        else:
            raise RuntimeError(f"get_image failed: {result}")


def main():
    global finger
    uart = serial.Serial(config.FINGERPRINT_PORT, baudrate=config.FINGERPRINT_BAUD, timeout=1)
    finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

    slot = config.OWNER_FINGERPRINT_ID
    print(f"Enrolling {config.OWNER_NAME} into fingerprint slot {slot}.")

    get_fingerprint_image("Place finger on sensor, then press Enter...")
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        raise RuntimeError("Could not process first scan.")

    get_fingerprint_image("Remove finger, then place the SAME finger again and press Enter...")
    if finger.image_2_tz(2) != adafruit_fingerprint.OK:
        raise RuntimeError("Could not process second scan.")

    if finger.create_model() != adafruit_fingerprint.OK:
        raise RuntimeError("Fingerprints did not match each other -- try again.")

    if finger.store_model(slot) != adafruit_fingerprint.OK:
        raise RuntimeError(f"Could not store model in slot {slot}.")

    print(f"Done. {config.OWNER_NAME}'s fingerprint stored in slot {slot}.")
    print("Make sure OWNER_FINGERPRINT_ID in your .env matches this slot.")


if __name__ == "__main__":
    main()

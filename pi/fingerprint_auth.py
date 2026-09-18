"""R307 fingerprint check via the Adafruit fingerprint protocol over UART.

Wiring (use a USB-to-TTL adapter, not the Pi's own UART pins directly --
it keeps Bluetooth/console-UART conflicts and 3.3V/5V mismatches out of
the picture entirely):
  R307 VCC -> 5V (or 3.3V, check your module's silkscreen)
  R307 GND -> GND (common ground with the Pi)
  R307 TX  -> adapter RX
  R307 RX  -> adapter TX
"""
import time
import serial
import adafruit_fingerprint
import config


class FingerprintResult:
    def __init__(self, matched, confidence=None, reason=None):
        self.matched = matched
        self.confidence = confidence
        self.reason = reason


def _connect():
    uart = serial.Serial(config.FINGERPRINT_PORT, baudrate=config.FINGERPRINT_BAUD, timeout=1)
    return adafruit_fingerprint.Adafruit_Fingerprint(uart)


def verify_owner(timeout=None):
    """Waits for a finger, matches it against the enrolled owner slot only.

    A match against ANY other stored template, or no match at all, counts
    as a failure -- we only ever accept config.OWNER_FINGERPRINT_ID.
    """
    timeout = timeout if timeout is not None else config.FINGERPRINT_TIMEOUT_S
    try:
        finger = _connect()
    except Exception as e:
        return FingerprintResult(False, reason=f"sensor_unavailable: {e}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        if finger.get_image() == adafruit_fingerprint.OK:
            break
        time.sleep(0.1)
    else:
        return FingerprintResult(False, reason="timeout_waiting_for_finger")

    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        return FingerprintResult(False, reason="image_conversion_failed")

    if finger.finger_search() != adafruit_fingerprint.OK:
        return FingerprintResult(False, reason="no_match_in_database")

    matched_id = finger.finger_id
    confidence = finger.confidence
    if matched_id != config.OWNER_FINGERPRINT_ID:
        return FingerprintResult(False, confidence=confidence, reason=f"matched_wrong_slot_{matched_id}")

    return FingerprintResult(True, confidence=confidence)

"""Stubs out every hardware-touching module (gpiozero/serial/adafruit_fingerprint/
cv2/picamera2 aren't installed on a dev machine, and shouldn't be needed to
verify the orchestration logic) so access_control.py can be imported and
driven with plain mocks standing in for gpio_io / fingerprint_auth / face_auth.
"""
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

for name in ("gpio_io", "fingerprint_auth", "face_auth"):
    sys.modules[name] = MagicMock(name=name)

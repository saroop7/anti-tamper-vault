"""Face check via the Pi Camera + OpenCV LBPH recognizer.

This is the SECOND factor, run only after the fingerprint already matched
the owner's slot -- it does not need to be as strong as the fingerprint
check on its own, just hard to fool with a random passerby's face.
"""
import os
import time
import cv2
import numpy as np
import config

_recognizer = None
_cascade = None


def _load():
    global _recognizer, _cascade
    if _recognizer is None:
        if not os.path.exists(config.FACE_MODEL_PATH):
            raise RuntimeError(
                f"No trained face model at {config.FACE_MODEL_PATH}. Run enroll_face.py first."
            )
        _recognizer = cv2.face.LBPHFaceRecognizer_create()
        _recognizer.read(config.FACE_MODEL_PATH)
    if _cascade is None:
        _cascade = cv2.CascadeClassifier(config.FACE_CASCADE_PATH)
        if _cascade.empty():
            raise RuntimeError(f"Could not load Haar cascade from {config.FACE_CASCADE_PATH}")


def _capture_gray_frame():
    from picamera2 import Picamera2

    picam2 = Picamera2()
    cfg = picam2.create_still_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam2.configure(cfg)
    picam2.start()
    time.sleep(0.5)  # let auto-exposure settle
    frame = picam2.capture_array()
    picam2.stop()
    picam2.close()
    return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)


class FaceResult:
    def __init__(self, matched, confidence=None, reason=None):
        self.matched = matched
        self.confidence = confidence
        self.reason = reason


def verify_owner(timeout=None):
    timeout = timeout if timeout is not None else config.FACE_TIMEOUT_S
    try:
        _load()
    except Exception as e:
        return FaceResult(False, reason=str(e))

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            gray = _capture_gray_frame()
        except Exception as e:
            return FaceResult(False, reason=f"camera_error: {e}")

        faces = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
        if len(faces) == 0:
            time.sleep(0.3)
            continue

        # largest detected face = whoever is closest to the camera
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        roi = cv2.resize(gray[y:y + h, x:x + w], (200, 200))

        label, confidence = _recognizer.predict(roi)
        # LBPH: LOWER confidence == better match
        if label == 0 and confidence <= config.FACE_CONFIDENCE_MAX:
            return FaceResult(True, confidence=confidence)
        return FaceResult(False, confidence=confidence, reason="face_no_match")

    return FaceResult(False, reason="timeout_no_face_detected")

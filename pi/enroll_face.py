"""Run this once to capture Mr Sarkar's face and train the LBPH model used
by face_auth.py. Captures ~30 samples from a few angles/lighting to make the
model more robust, then writes config.FACE_MODEL_PATH.

Usage: python3 enroll_face.py
"""
import time
import cv2
import numpy as np
import config

SAMPLES = 30
OWNER_LABEL = 0  # single-owner model; label 0 == config.OWNER_NAME


def main():
    from picamera2 import Picamera2

    cascade = cv2.CascadeClassifier(config.FACE_CASCADE_PATH)
    if cascade.empty():
        raise RuntimeError(f"Could not load Haar cascade from {config.FACE_CASCADE_PATH}")

    picam2 = Picamera2()
    cfg = picam2.create_still_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam2.configure(cfg)
    picam2.start()
    time.sleep(1)

    print(f"Capturing {SAMPLES} face samples for {config.OWNER_NAME}.")
    print("Move your head slightly (angle, distance, expression) between shots.")

    faces = []
    labels = []
    collected = 0
    while collected < SAMPLES:
        frame = picam2.capture_array()
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        detections = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
        if len(detections) == 0:
            time.sleep(0.2)
            continue

        x, y, w, h = max(detections, key=lambda f: f[2] * f[3])
        roi = cv2.resize(gray[y:y + h, x:x + w], (200, 200))
        faces.append(roi)
        labels.append(OWNER_LABEL)
        collected += 1
        print(f"  captured {collected}/{SAMPLES}")
        time.sleep(0.4)

    picam2.stop()
    picam2.close()

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels))
    recognizer.write(config.FACE_MODEL_PATH)
    print(f"Done. Model saved to {config.FACE_MODEL_PATH}")
    print("Tune FACE_CONFIDENCE_MAX in .env if false accepts/rejects happen -- "
          "lower = stricter match required.")


if __name__ == "__main__":
    main()

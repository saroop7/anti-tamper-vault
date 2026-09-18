"""Central config for the vault access-control service.

Everything here is overridable via environment variables (see .env.example)
so pins/timings/windows can change without touching code.
"""
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

def _int(name, default):
    return int(os.getenv(name, default))

def _bool(name, default):
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")

# ---- identity ---------------------------------------------------------
DEVICE_ID = os.getenv("DEVICE_ID", "vault-pi-01")
OWNER_NAME = os.getenv("OWNER_NAME", "Mr Sarkar")
OWNER_FINGERPRINT_ID = _int("OWNER_FINGERPRINT_ID", 1)  # slot on the R307's onboard flash

# ---- allowed access windows --------------------------------------------
# "days" is a set of Python weekday() ints: Mon=0 ... Sun=6. Empty/omitted = every day.
TIMEZONE = ZoneInfo(os.getenv("VAULT_TZ", "Asia/Kolkata"))
ACCESS_WINDOWS = [
    {"start": os.getenv("WINDOW_START", "10:00"), "end": os.getenv("WINDOW_END", "11:00"), "days": set()},
]

# ---- GPIO pins (BCM numbering) -----------------------------------------
BUTTON_PIN = _int("BUTTON_PIN", 17)       # "request access" push button, pulled up internally
RELAY_PIN = _int("RELAY_PIN", 27)         # drives the lock relay module
RELAY_ACTIVE_HIGH = _bool("RELAY_ACTIVE_HIGH", False)  # most cheap relay boards are active-low
SIREN_PIN = _int("SIREN_PIN", 22)
LED_GREEN_PIN = _int("LED_GREEN_PIN", 23)
LED_RED_PIN = _int("LED_RED_PIN", 24)

# ---- fingerprint sensor (R307 over UART) -------------------------------
FINGERPRINT_PORT = os.getenv("FINGERPRINT_PORT", "/dev/ttyUSB0")  # USB-TTL adapter recommended
FINGERPRINT_BAUD = _int("FINGERPRINT_BAUD", 57600)
FINGERPRINT_TIMEOUT_S = _int("FINGERPRINT_TIMEOUT_S", 10)

# ---- face check (Pi Camera + OpenCV LBPH) ------------------------------
FACE_MODEL_PATH = os.getenv("FACE_MODEL_PATH", os.path.join(os.path.dirname(__file__), "owner_face_model.yml"))
FACE_CASCADE_PATH = os.getenv(
    "FACE_CASCADE_PATH",
    "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
)
FACE_CONFIDENCE_MAX = float(os.getenv("FACE_CONFIDENCE_MAX", "70"))  # LBPH distance; lower = stricter
FACE_TIMEOUT_S = _int("FACE_TIMEOUT_S", 8)

# ---- lock / alert timings ----------------------------------------------
UNLOCK_SECONDS = _int("UNLOCK_SECONDS", 5)
SIREN_SECONDS = _int("SIREN_SECONDS", 8)
LOCKOUT_ATTEMPTS = _int("LOCKOUT_ATTEMPTS", 3)      # denials within LOCKOUT_WINDOW_S...
LOCKOUT_WINDOW_S = _int("LOCKOUT_WINDOW_S", 300)    # ...trigger an extended lockout
LOCKOUT_SECONDS = _int("LOCKOUT_SECONDS", 900)

# ---- backend (your existing Node/Express ledger) -----------------------
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")
INGEST_API_KEY = os.getenv("INGEST_API_KEY", "some-long-random-string")
BACKEND_TIMEOUT_S = _int("BACKEND_TIMEOUT_S", 5)

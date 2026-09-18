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

# ---- servo release latch (pigpio PWM, BCM numbering) --------------------
# Runs *alongside* the existing relay in gpio_io.unlock() -- if your box
# only has a servo and no relay, leave RELAY_PIN wired to nothing unused.
SERVO_PIN = _int("SERVO_PIN", 12)
SERVO_LOCKED_PULSE_US = _int("SERVO_LOCKED_PULSE_US", 500)    # ~0 degrees
SERVO_OPEN_PULSE_US = _int("SERVO_OPEN_PULSE_US", 1500)       # ~90 degrees

# ---- RTC (DS3231, I2C bus 1) --------------------------------------------
RTC_I2C_ADDR = _int("RTC_I2C_ADDR", 0x68)

# ---- TFT display (ST7735, hardware SPI0 CE0 + these two GPIO) -----------
TFT_DC_PIN = _int("TFT_DC_PIN", 5)
TFT_RST_PIN = _int("TFT_RST_PIN", 6)

# ---- tamper accelerometer (ADXL345, I2C bus 1) ---------------------------
ADXL_I2C_ADDR = _int("ADXL_I2C_ADDR", 0x53)
TAMPER_ACCEL_THRESHOLD_G = float(os.getenv("TAMPER_ACCEL_THRESHOLD_G", "0.5"))
TAMPER_POLL_INTERVAL_S = float(os.getenv("TAMPER_POLL_INTERVAL_S", "0.3"))

# Optional digital lid switch -- leave unset if you don't have one wired;
# tamper_monitor then just reports "unknown" instead of open/closed.
LID_SWITCH_PIN = os.getenv("LID_SWITCH_PIN")
LID_SWITCH_PIN = int(LID_SWITCH_PIN) if LID_SWITCH_PIN else None

# ---- SIM800L SMS alert (soft serial via pigpio, BCM numbering) ----------
SIM_TX_PIN = _int("SIM_TX_PIN", 21)
SIM_RX_PIN = _int("SIM_RX_PIN", 20)
# Comma-separated list of E.164 Indian numbers, e.g. "+918122370613,+917601068528"
SMS_ALERT_NUMBERS = [n.strip() for n in os.getenv("SMS_ALERT_NUMBERS", "+918122370613,+917601068528").split(",") if n.strip()]

# ---- last-known GPS fix (static for now -- wire a GPS module later) -----
DEFAULT_LAT = float(os.getenv("DEFAULT_LAT", "12.9716"))
DEFAULT_LNG = float(os.getenv("DEFAULT_LNG", "77.5946"))

# ---- frontend-triggered enrollment queue --------------------------------
ENROLLMENT_POLL_INTERVAL_S = float(os.getenv("ENROLLMENT_POLL_INTERVAL_S", "3"))

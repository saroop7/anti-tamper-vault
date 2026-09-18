"""GPIO wrappers for the lock relay, siren, status LEDs and request button."""
import time
from gpiozero import OutputDevice, Button
import config

_button = Button(config.BUTTON_PIN, pull_up=True, bounce_time=0.05)
_relay = OutputDevice(config.RELAY_PIN, active_high=config.RELAY_ACTIVE_HIGH, initial_value=False)
_siren = OutputDevice(config.SIREN_PIN, initial_value=False)
_led_green = OutputDevice(config.LED_GREEN_PIN, initial_value=False)
_led_red = OutputDevice(config.LED_RED_PIN, initial_value=False)

# Servo release latch -- separate from gpiozero above since it needs PWM,
# shared with the pigpio daemon that also drives the SIM800L soft serial.
# Optional: if pigpiod isn't running, unlock() just skips the servo pulse
# and the relay alone still does its job.
try:
    import pigpio
    _servo_pi = pigpio.pi()
    if not _servo_pi.connected:
        raise RuntimeError("pigpiod not running")
    _servo_pi.set_PWM_frequency(config.SERVO_PIN, 50)
    _servo_pi.set_servo_pulsewidth(config.SERVO_PIN, config.SERVO_LOCKED_PULSE_US)
    _servo_available = True
except Exception as e:
    print(f"[gpio_io] servo unavailable, relay-only unlock: {e}")
    _servo_pi = None
    _servo_available = False


def wait_for_request():
    """Blocks until the access-request button is pressed."""
    _button.wait_for_press()


def unlock(seconds=None):
    seconds = seconds if seconds is not None else config.UNLOCK_SECONDS
    _led_green.on()
    _relay.on()
    if _servo_available:
        _servo_pi.set_servo_pulsewidth(config.SERVO_PIN, config.SERVO_OPEN_PULSE_US)  # rotate ~90deg
    time.sleep(seconds)
    if _servo_available:
        _servo_pi.set_servo_pulsewidth(config.SERVO_PIN, config.SERVO_LOCKED_PULSE_US)  # back to 0deg
    _relay.off()
    set_secure_idle()


def alert(seconds=None):
    """Siren + red LED for a denied/tampered attempt."""
    seconds = seconds if seconds is not None else config.SIREN_SECONDS
    _led_green.off()
    _led_red.on()
    _siren.on()
    time.sleep(seconds)
    _siren.off()
    set_secure_idle()


def alert_start():
    """Non-blocking siren/LED on — used for indefinite lockouts and the
    continuous tamper monitor (tamper_monitor.py)."""
    _led_green.off()
    _led_red.on()
    _siren.on()


def alert_stop():
    _siren.off()
    set_secure_idle()


def set_secure_idle():
    """Baseline state: box not tampered, not mid access-flow -- steady
    green LED, red off. Call once at startup and after any alert clears."""
    _led_red.off()
    _led_green.on()


def blink_waiting(times=2):
    """Short green blink to prompt 'place finger now', etc."""
    for _ in range(times):
        _led_green.off()
        time.sleep(0.15)
        _led_green.on()
        time.sleep(0.15)

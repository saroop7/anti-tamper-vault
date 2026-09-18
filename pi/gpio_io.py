"""GPIO wrappers for the lock relay, siren, status LEDs and request button."""
import time
from gpiozero import OutputDevice, Button
import config

_button = Button(config.BUTTON_PIN, pull_up=True, bounce_time=0.05)
_relay = OutputDevice(config.RELAY_PIN, active_high=config.RELAY_ACTIVE_HIGH, initial_value=False)
_siren = OutputDevice(config.SIREN_PIN, initial_value=False)
_led_green = OutputDevice(config.LED_GREEN_PIN, initial_value=False)
_led_red = OutputDevice(config.LED_RED_PIN, initial_value=False)


def wait_for_request():
    """Blocks until the access-request button is pressed."""
    _button.wait_for_press()


def unlock(seconds=None):
    seconds = seconds if seconds is not None else config.UNLOCK_SECONDS
    _led_green.on()
    _relay.on()
    time.sleep(seconds)
    _relay.off()
    _led_green.off()


def alert(seconds=None):
    """Siren + red LED for a denied/tampered attempt."""
    seconds = seconds if seconds is not None else config.SIREN_SECONDS
    _led_red.on()
    _siren.on()
    time.sleep(seconds)
    _siren.off()
    _led_red.off()


def alert_start():
    """Non-blocking siren/LED on — used for indefinite lockouts."""
    _led_red.on()
    _siren.on()


def alert_stop():
    _siren.off()
    _led_red.off()


def blink_waiting(times=2):
    """Short green blink to prompt 'place finger now', etc."""
    for _ in range(times):
        _led_green.on()
        time.sleep(0.15)
        _led_green.off()
        time.sleep(0.15)

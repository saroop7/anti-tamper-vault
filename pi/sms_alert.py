"""Sends tamper-alert SMS via a SIM800L on soft (bit-banged) serial.

Uses pigpio's waveform serial output rather than a UART, since the R307
fingerprint sensor already owns the hardware UART (/dev/serial0) -- see
config.SIM_TX_PIN / SIM_RX_PIN for the two free GPIO this bit-bangs on.
"""
import time

import config

try:
    import pigpio
    _pi = pigpio.pi()
    if not _pi.connected:
        raise RuntimeError("pigpiod not running -- `sudo systemctl start pigpiod`")
    _pi.set_mode(config.SIM_TX_PIN, pigpio.OUTPUT)
    _available = True
except Exception as e:
    print(f"[sms_alert] SIM800L link unavailable: {e}")
    _pi = None
    _available = False


def send_tamper_sms(lat, lng, numbers=None):
    """Fire-and-forget: sends the same tamper SMS to every number in the list.

    Never raises -- a failed SMS shouldn't crash the tamper-response path,
    the event is already logged to the backend regardless.
    """
    numbers = numbers or config.SMS_ALERT_NUMBERS
    if not _available:
        print(f"[sms_alert] skipped (no SIM800L link) -- would have alerted {numbers}")
        return

    msg = f"TAMPER ALERT! Vault breached. Lat: {lat}, Lng: {lng}"
    for num in numbers:
        try:
            _pi.wave_clear()
            cmds = f'AT+CMGF=1\r\nAT+CMGS="{num}"\r\n{msg}\x1A\r\n'
            _pi.wave_add_serial(config.SIM_TX_PIN, 9600, cmds.encode("utf-8"))
            wid = _pi.wave_create()
            _pi.wave_send_once(wid)
            time.sleep(3)  # let the module finish transmitting before the next AT command
        except Exception as e:
            print(f"[sms_alert] failed to send to {num}: {e}")
    print(f"[sms_alert] tamper SMS dispatched to {numbers}")

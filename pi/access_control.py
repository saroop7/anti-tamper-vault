"""Main vault access-control loop.

Flow on every button press:
  1. Time window check -- outside 10:00-11:00 (configurable), deny outright.
  2. Fingerprint check -- must match the owner's enrolled R307 slot.
  3. Face check -- must match the trained owner face model.
  4. All three pass -> unlock the relay for UNLOCK_SECONDS.
     Anything fails -> siren + red LED, and the attempt is logged to the
     backend ledger exactly like a tamper event (tamper=true).

Repeated denials within LOCKOUT_WINDOW_S trip an extended lockout (siren
stays on until manually reset) instead of a short burst -- makes brute
forcing the sensors loud and obvious rather than something to quietly retry.
"""
import time
from collections import deque
from datetime import datetime, timezone

import config
import gpio_io
import fingerprint_auth
import face_auth
import backend_client
import tamper_monitor
import enrollment_worker
import tft_display
from time_window import is_within_window

_recent_denials = deque()  # timestamps of denials, for lockout tracking


def _now_iso():
    # Must match JS's `new Date().toISOString()` exactly (UTC, millisecond
    # precision, trailing "Z") -- the backend's /verify route recomputes the
    # event hash from a Postgres-round-tripped device_ts via that same JS
    # call, so any other format (e.g. Python's default isoformat(), which
    # keeps microseconds and a local offset) makes the hash unverifiable
    # forever even though nothing was actually tampered with.
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _record_denial_and_check_lockout():
    now = time.time()
    _recent_denials.append(now)
    while _recent_denials and now - _recent_denials[0] > config.LOCKOUT_WINDOW_S:
        _recent_denials.popleft()
    return len(_recent_denials) >= config.LOCKOUT_ATTEMPTS


def deny(reason, extra=None):
    print(f"[access_control] DENIED: {reason}")
    sensor_data = {"reason": reason, "owner": config.OWNER_NAME}
    if extra:
        sensor_data.update(extra)
    backend_client.log_event(status=f"access_denied:{reason}", tamper=True,
                              device_ts=_now_iso(), sensor_data=sensor_data)

    if _record_denial_and_check_lockout():
        print(f"[access_control] LOCKOUT triggered ({config.LOCKOUT_ATTEMPTS} denials "
              f"in {config.LOCKOUT_WINDOW_S}s) -- siren on for {config.LOCKOUT_SECONDS}s")
        backend_client.log_event(status="lockout_triggered", tamper=True,
                                  device_ts=_now_iso(), sensor_data={"denials": len(_recent_denials)})
        gpio_io.alert_start()
        time.sleep(config.LOCKOUT_SECONDS)
        gpio_io.alert_stop()
        _recent_denials.clear()
    else:
        gpio_io.alert()


def grant():
    print("[access_control] GRANTED -- unlocking")
    backend_client.log_event(status="access_granted", tamper=False,
                              device_ts=_now_iso(), sensor_data={"owner": config.OWNER_NAME})
    from rtc_clock import now as _rtc_now
    tft_display.update(_rtc_now(), "SUCCESSFUL ENTRY")
    gpio_io.unlock()


def handle_access_request():
    now = datetime.now(config.TIMEZONE)
    print(f"[access_control] request received at {now.isoformat()}")

    if not is_within_window(now):
        deny("outside_time_window", {"attempted_at": now.isoformat()})
        return

    gpio_io.blink_waiting()
    fp = fingerprint_auth.verify_owner()
    if not fp.matched:
        deny("fingerprint_mismatch", {"fp_reason": fp.reason, "confidence": fp.confidence})
        return

    face = face_auth.verify_owner()
    if not face.matched:
        deny("face_mismatch", {"face_reason": face.reason, "confidence": face.confidence})
        return

    grant()


def main():
    print(f"[access_control] ready -- owner={config.OWNER_NAME}, "
          f"windows={config.ACCESS_WINDOWS}, device_id={config.DEVICE_ID}")
    tamper_monitor.start()  # RTC/TFT clock + continuous accelerometer watch,
                             # runs independently of the button-triggered flow below
    enrollment_worker.start()  # polls for frontend-triggered "add new user" requests
    while True:
        gpio_io.wait_for_request()
        try:
            handle_access_request()
        except Exception as e:
            print(f"[access_control] unexpected error: {e}")
            backend_client.log_event(status="access_control_error", tamper=True,
                                      device_ts=_now_iso(), sensor_data={"error": str(e)})
        time.sleep(0.5)  # debounce before accepting the next request


if __name__ == "__main__":
    main()

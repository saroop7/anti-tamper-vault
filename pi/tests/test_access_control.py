"""Drives access_control.handle_access_request() through every path with
gpio_io / fingerprint_auth / face_auth mocked out (see conftest.py) and
backend_client.log_event patched to a spy, so we verify the orchestration
logic (sequencing, lockout counting, event payloads) in isolation.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import config
import access_control


def _always_within_window():
    # Whole-day window -- these tests exercise fingerprint/face logic, not
    # the time boundary itself (see test_time_window.py for that), so avoid
    # any hour-wraparound edge cases near midnight.
    config.ACCESS_WINDOWS = [{"start": "00:00", "end": "23:59", "days": set()}]


def _outside_any_window():
    config.ACCESS_WINDOWS = [{"start": "00:00", "end": "00:01", "days": set()}]


def setup_function():
    access_control._recent_denials.clear()


def test_deny_outside_time_window():
    _outside_any_window()
    with patch("access_control.backend_client") as bc, \
         patch("access_control.gpio_io") as gp, \
         patch("access_control.fingerprint_auth") as fp:
        access_control.handle_access_request()
        gp.unlock.assert_not_called()
        gp.alert.assert_called_once()
        fp.verify_owner.assert_not_called()  # should short-circuit before touching the sensor
        status = bc.log_event.call_args.kwargs["status"]
        tamper = bc.log_event.call_args.kwargs["tamper"]
        assert status.startswith("access_denied:outside_time_window")
        assert tamper is True


def test_deny_fingerprint_mismatch():
    _always_within_window()
    with patch("access_control.backend_client") as bc, \
         patch("access_control.gpio_io") as gp, \
         patch("access_control.fingerprint_auth") as fp, \
         patch("access_control.face_auth") as face:
        fp.verify_owner.return_value = SimpleNamespace(matched=False, reason="no_match_in_database", confidence=None)
        access_control.handle_access_request()
        gp.unlock.assert_not_called()
        gp.alert.assert_called_once()
        face.verify_owner.assert_not_called()  # should short-circuit before the camera
        assert bc.log_event.call_args.kwargs["status"] == "access_denied:fingerprint_mismatch"
        assert bc.log_event.call_args.kwargs["tamper"] is True


def test_deny_face_mismatch():
    _always_within_window()
    with patch("access_control.backend_client") as bc, \
         patch("access_control.gpio_io") as gp, \
         patch("access_control.fingerprint_auth") as fp, \
         patch("access_control.face_auth") as face:
        fp.verify_owner.return_value = SimpleNamespace(matched=True, reason=None, confidence=55)
        face.verify_owner.return_value = SimpleNamespace(matched=False, reason="face_no_match", confidence=88)
        access_control.handle_access_request()
        gp.unlock.assert_not_called()
        gp.alert.assert_called_once()
        assert bc.log_event.call_args.kwargs["status"] == "access_denied:face_mismatch"
        assert bc.log_event.call_args.kwargs["tamper"] is True


def test_grant_when_everything_matches():
    _always_within_window()
    with patch("access_control.backend_client") as bc, \
         patch("access_control.gpio_io") as gp, \
         patch("access_control.fingerprint_auth") as fp, \
         patch("access_control.face_auth") as face:
        fp.verify_owner.return_value = SimpleNamespace(matched=True, reason=None, confidence=60)
        face.verify_owner.return_value = SimpleNamespace(matched=True, reason=None, confidence=40)
        access_control.handle_access_request()
        gp.unlock.assert_called_once()
        gp.alert.assert_not_called()
        assert bc.log_event.call_args.kwargs["status"] == "access_granted"
        assert bc.log_event.call_args.kwargs["tamper"] is False


def test_lockout_after_repeated_denials():
    _outside_any_window()
    config.LOCKOUT_ATTEMPTS = 3
    config.LOCKOUT_WINDOW_S = 300
    config.LOCKOUT_SECONDS = 0  # access_control.deny() really does time.sleep() this long on lockout
    with patch("access_control.backend_client") as bc, \
         patch("access_control.gpio_io") as gp, \
         patch("access_control.fingerprint_auth"):
        access_control.handle_access_request()
        access_control.handle_access_request()
        gp.alert.assert_called()          # short bursts for the first two denials
        gp.alert_start.assert_not_called()

        access_control.handle_access_request()  # 3rd denial in-window -> lockout
        gp.alert_start.assert_called_once()
        gp.alert_stop.assert_called_once()
        statuses = [c.kwargs["status"] for c in bc.log_event.call_args_list]
        assert "lockout_triggered" in statuses

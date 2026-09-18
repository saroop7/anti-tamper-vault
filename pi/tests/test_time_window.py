from datetime import datetime
import config
from time_window import is_within_window


def _at(h, m):
    return datetime(2026, 9, 17, h, m, tzinfo=config.TIMEZONE)


def test_inside_window():
    config.ACCESS_WINDOWS = [{"start": "10:00", "end": "11:00", "days": set()}]
    assert is_within_window(_at(10, 0)) is True
    assert is_within_window(_at(10, 30)) is True
    assert is_within_window(_at(11, 0)) is True


def test_outside_window():
    config.ACCESS_WINDOWS = [{"start": "10:00", "end": "11:00", "days": set()}]
    assert is_within_window(_at(9, 59)) is False
    assert is_within_window(_at(11, 1)) is False
    assert is_within_window(_at(23, 0)) is False


def test_day_restriction():
    # 2026-09-17 is a Thursday -> weekday() == 3
    config.ACCESS_WINDOWS = [{"start": "10:00", "end": "11:00", "days": {0, 1, 2}}]  # Mon-Wed only
    assert is_within_window(_at(10, 30)) is False

    config.ACCESS_WINDOWS = [{"start": "10:00", "end": "11:00", "days": {3}}]  # Thursday only
    assert is_within_window(_at(10, 30)) is True


def test_multiple_windows():
    config.ACCESS_WINDOWS = [
        {"start": "10:00", "end": "11:00", "days": set()},
        {"start": "18:00", "end": "19:00", "days": set()},
    ]
    assert is_within_window(_at(10, 15)) is True
    assert is_within_window(_at(18, 15)) is True
    assert is_within_window(_at(14, 0)) is False

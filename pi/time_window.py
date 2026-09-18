"""Is `now` inside one of the configured access windows?"""
from datetime import datetime
import config


def _parse_hm(s):
    h, m = s.split(":")
    return int(h), int(m)


def is_within_window(now=None):
    now = now or datetime.now(config.TIMEZONE)
    for window in config.ACCESS_WINDOWS:
        days = window.get("days") or set()
        if days and now.weekday() not in days:
            continue
        sh, sm = _parse_hm(window["start"])
        eh, em = _parse_hm(window["end"])
        start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
        if start <= now <= end:
            return True
    return False

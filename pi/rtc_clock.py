"""DS3231 real-time clock over I2C, with a system-clock fallback.

The RTC keeps time across power loss (coin-cell backed), which the Pi's own
clock can't do without network access on boot -- useful since the vault's
access windows depend on wall-clock time being correct even if it powers up
offline.
"""
from datetime import datetime

import config

try:
    from smbus2 import SMBus
    _bus = SMBus(1)
except Exception as e:
    print(f"[rtc_clock] I2C bus unavailable, falling back to system clock: {e}")
    _bus = None


def _bcd_to_dec(b):
    return (b & 0x0F) + ((b >> 4) * 10)


def now():
    """Returns a timezone-aware datetime in config.TIMEZONE.

    Falls back to the system clock if the RTC isn't wired/responding, so a
    missing RTC degrades gracefully instead of crashing the daemon.
    """
    if _bus is not None:
        try:
            data = _bus.read_i2c_block_data(config.RTC_I2C_ADDR, 0x00, 7)
            second = _bcd_to_dec(data[0] & 0x7F)
            minute = _bcd_to_dec(data[1])
            hour = _bcd_to_dec(data[2] & 0x3F)  # 24-hour mode
            day = _bcd_to_dec(data[4])
            month = _bcd_to_dec(data[5] & 0x1F)
            year = 2000 + _bcd_to_dec(data[6])
            return datetime(year, month, day, hour, minute, second, tzinfo=config.TIMEZONE)
        except Exception as e:
            print(f"[rtc_clock] read failed, falling back to system clock: {e}")

    return datetime.now(config.TIMEZONE)

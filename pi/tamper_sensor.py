"""ADXL345 accelerometer over I2C -- flags a tamper event on sudden movement.

Reads the delta from resting gravity (~1g on one axis) rather than raw
acceleration, so the box sitting still doesn't itself read as "vibration."
"""
import config

try:
    from smbus2 import SMBus
    _bus = SMBus(1)
    # Power on (measure mode) + enable full-resolution +-16g range.
    _bus.write_byte_data(config.ADXL_I2C_ADDR, 0x2D, 0x08)
    _bus.write_byte_data(config.ADXL_I2C_ADDR, 0x31, 0x09)
    _available = True
except Exception as e:
    print(f"[tamper_sensor] ADXL345 unavailable: {e}")
    _bus = None
    _available = False


def read_delta_g():
    """Returns |acceleration - 1g| on the X axis, in g. 0.0 if sensor is down."""
    if not _available:
        return 0.0
    try:
        data = _bus.read_i2c_block_data(config.ADXL_I2C_ADDR, 0x32, 6)
        raw = (data[1] << 8) | data[0]
        if raw > 32767:
            raw -= 65536
        g = raw * 0.0039  # LSB scale at full-res +-16g
        return round(abs(g - 1.0), 3)
    except Exception as e:
        print(f"[tamper_sensor] read failed: {e}")
        return 0.0


def is_tamper(delta_g=None):
    delta_g = read_delta_g() if delta_g is None else delta_g
    return delta_g > config.TAMPER_ACCEL_THRESHOLD_G

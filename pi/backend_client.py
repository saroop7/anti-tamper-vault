"""Fire-and-forget event logging to the existing Node backend's /events ledger.

Runs on a background thread so a slow/unreachable network never delays the
physical response (lock stays shut / siren fires immediately regardless).
"""
import threading
import requests
import config


def _post(payload):
    try:
        requests.post(
            f"{config.BACKEND_URL}/events",
            json=payload,
            headers={"x-api-key": config.INGEST_API_KEY},
            timeout=config.BACKEND_TIMEOUT_S,
        )
    except requests.RequestException as e:
        print(f"[backend_client] failed to log event: {e}")


def log_event(status, tamper, device_ts, sensor_data=None, lat=None, lng=None):
    payload = {
        "device_id": config.DEVICE_ID,
        "device_ts": device_ts,
        "status": status,
        "tamper": tamper,
        "sensor_data": sensor_data or {},
    }
    # The backend rejects an explicit null for lat/lng ("lat must be a
    # number") -- omit the keys entirely rather than sending None.
    if lat is not None:
        payload["lat"] = lat
    if lng is not None:
        payload["lng"] = lng
    threading.Thread(target=_post, args=(payload,), daemon=True).start()

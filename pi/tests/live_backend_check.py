"""One-off live integration check: drives access_control.handle_access_request()
with gpio_io/fingerprint_auth/face_auth mocked, but backend_client left REAL so
it makes an actual HTTP POST to a running backend instance. Confirms the wire
format access_control.py -> backend_client.py -> Express /events actually
round-trips correctly (not just that the mocks were called with the right args).

Reads INGEST_API_KEY out of ../backend/.env in-process via dotenv_values() so
the key never has to be echoed/printed/grepped through a shell command.
"""
import os
import sys
import time
from unittest.mock import patch
from types import SimpleNamespace
from dotenv import dotenv_values

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

backend_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))
os.environ["INGEST_API_KEY"] = backend_env["INGEST_API_KEY"]
os.environ["BACKEND_URL"] = "http://localhost:3099"
os.environ["DEVICE_ID"] = "vault-pi-01-livetest"

from unittest.mock import MagicMock
sys.modules["gpio_io"] = MagicMock(name="gpio_io")
sys.modules["fingerprint_auth"] = MagicMock(name="fingerprint_auth")
sys.modules["face_auth"] = MagicMock(name="face_auth")

import config
import access_control
import requests

print(f"BACKEND_URL={config.BACKEND_URL}  DEVICE_ID={config.DEVICE_ID}")

# ---- 1. GRANT path: real HTTP POST, tamper=false, no chain cost -----------
config.ACCESS_WINDOWS = [{"start": "00:00", "end": "23:59", "days": set()}]
with patch("access_control.gpio_io") as gp, \
     patch("access_control.fingerprint_auth") as fp, \
     patch("access_control.face_auth") as face:
    fp.verify_owner.return_value = SimpleNamespace(matched=True, reason=None, confidence=60)
    face.verify_owner.return_value = SimpleNamespace(matched=True, reason=None, confidence=40)
    access_control.handle_access_request()
    assert gp.unlock.called, "expected unlock() to fire on grant"

time.sleep(0.5)  # let the background logging thread land

# ---- verify the grant event landed correctly, and dbMatch is now fixed ----
# (skipping the deny/tamper path here on purpose -- it already anchored fine
# on-chain in the previous run; re-running it would just spend another real
# Sepolia tx to re-prove the same anchor behavior, which we don't need to.)
rows = requests.get(f"{config.BACKEND_URL}/events").json()
mine = [r for r in rows if r["device_id"] == "vault-pi-01-livetest"]
print(f"found {len(mine)} events from this run:")
for r in mine:
    print(f"  id={r['id']} status={r['status']} tamper={r['tamper']} onchain_tx={r['onchain_tx']}")

granted = sorted((r for r in mine if r["status"] == "access_granted"), key=lambda r: r["id"])
assert granted and granted[-1]["tamper"] is False, "grant event missing or malformed"
latest = granted[-1]

v = requests.get(f"{config.BACKEND_URL}/events/{latest['id']}/verify").json()
print(f"verify on grant event: {v}")
assert v["dbMatch"] is True, "hash recomputation mismatch -- data integrity broken"

print("\nLIVE INTEGRATION CHECK: PASS")

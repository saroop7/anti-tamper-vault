# Vault access control (Raspberry Pi 3B+)

Gates the physical lock on a time window (default **10:00-11:00 Asia/Kolkata,
every day**) AND owner identity (R307 fingerprint + Pi Camera face check).
Anyone outside the window, or a fingerprint/face that isn't the enrolled
owner, is denied and logged to the existing Node backend (`../backend`)
exactly like a tamper event — it'll show up in the dashboard ledger with
`tamper: true`.

This runs standalone on the Pi; it is separate from `../backend` (which
keeps doing what it already does — Postgres storage + optional on-chain
anchoring). This service just POSTs to it.

## Wiring

| Component | Pi 3B+ connection |
|---|---|
| Request button | GPIO17 (BCM) to GND, internal pull-up used — no resistor needed |
| Lock relay module (IN) | GPIO27 (BCM) |
| Relay VCC/GND | 5V / GND |
| Relay COM/NO | wired to your lock's power switch leg (solenoid/electromagnetic lock) |
| Siren/buzzer | via a relay or transistor on GPIO22 (BCM) — don't drive a siren directly off a GPIO pin |
| Green LED | GPIO23 (BCM) + resistor, to GND |
| Red LED | GPIO24 (BCM) + resistor, to GND |
| R307 fingerprint sensor | **USB-to-TTL adapter recommended**, not the Pi's own UART pins — avoids conflicts with the Pi's console/Bluetooth UART and voltage mismatches. VCC/GND to sensor, TX↔RX crossed to the adapter, adapter into a Pi USB port. Default `/dev/ttyUSB0`. |
| Pi Camera (rev 1.3) | Ribbon cable into the Pi's CSI port |

Double-check your specific relay board's polarity — most cheap boards are
**active-low** (a LOW signal energizes the relay), which is why
`RELAY_ACTIVE_HIGH=false` is the default in `.env.example`. Same idea for
the lock: never wire the Pi's 3.3V logic pins directly into a 12V solenoid
circuit — the relay is what isolates them.

## Setup

```bash
sudo apt update
sudo apt install -y python3-venv python3-opencv python3-picamera2 libatlas-base-dev
cd pi
python3 -m venv --system-site-packages venv   # --system-site-packages to reuse apt's picamera2
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: confirm pins, BACKEND_URL, and that INGEST_API_KEY matches backend/.env
```

Enable the camera and, if using the Pi's own UART instead of a USB adapter,
serial hardware, via `sudo raspi-config` (Interface Options).

## Enroll the owner (Mr Sarkar) — run once each

```bash
python3 enroll_fingerprint.py   # scans the same finger twice, stores to R307 slot 1
python3 enroll_face.py          # captures ~30 face samples, trains owner_face_model.yml
```

Re-run either script any time to re-enroll (fingerprint enrollment
overwrites the same slot; face enrollment overwrites the model file).

## Run it

```bash
python3 access_control.py
```

Press the request button. Outside the configured window it's denied
immediately. Inside the window: scan finger, then look at the camera. Both
must match the enrolled owner or it's denied. Either kind of denial fires
the siren/LED and logs the attempt to the backend; three denials within 5
minutes (`LOCKOUT_ATTEMPTS`/`LOCKOUT_WINDOW_S`) trip an extended lockout
where the siren stays on continuously instead of a short burst.

## Run as a service (auto-start on boot)

```bash
sudo cp systemd/vault-access.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vault-access
journalctl -u vault-access -f   # logs
```

Edit the `WorkingDirectory`/`ExecStart` paths in the unit file first if your
checkout isn't at `/home/pi/Anti-tamper-vault`.

## Tuning

- **Window**: edit `WINDOW_START`/`WINDOW_END` in `.env`, or edit
  `config.ACCESS_WINDOWS` directly in `config.py` for multiple windows or
  specific days (`"days": {0,1,2,3,4}` for Mon-Fri, weekday() numbering).
- **Face strictness**: `FACE_CONFIDENCE_MAX` in `.env` — LBPH distance,
  lower is stricter. If real access attempts get face-rejected, raise it a
  bit; if a stranger's face gets accepted, lower it and re-enroll with more
  varied samples.
- **Lockout**: `LOCKOUT_ATTEMPTS`, `LOCKOUT_WINDOW_S`, `LOCKOUT_SECONDS`.

## Notes

- The Pi is the source of truth for the time window and identity check —
  it works even if the backend/network is down. Logging to the backend is
  fire-and-forget on a background thread so a slow network never delays
  the lock/siren response.
- Face recognition here (OpenCV LBPH) is intentionally the lighter-weight
  option since it runs on a Pi 3B+ — it's the second factor after
  fingerprint, not the sole gate.

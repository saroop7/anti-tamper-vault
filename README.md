# anti-tamper-vault
# Anti-Tamper Vault

A physical vault access-control system with a tamper-evident, on-chain event
ledger. A Raspberry Pi gates the lock on a time window and two-factor
identity (fingerprint + face); every access attempt and tamper event is
logged to a backend, hashed, and — for tamper events — anchored to an
Ethereum smart contract so the log can't be quietly edited after the fact.

## How it fits together

```
┌─────────────┐      HTTPS       ┌─────────────┐      RPC       ┌──────────────┐
│  pi/        │ ───────────────► │  backend/   │ ──────────────►│  contracts/  │
│  Raspberry  │  POST /events    │  Node +     │  logEvent()     │  Vault.sol   │
│  Pi 3B+     │  (x-api-key)     │  Express +  │                 │  (Ethereum)  │
│  lock +     │                  │  Postgres   │                 │              │
│  sensors    │                  └──────┬──────┘                 └──────────────┘
└─────────────┘                         │ GET /events
                                         ▼
                                  ┌─────────────┐
                                  │  frontend/  │
                                  │  index.html │
                                  │  dashboard  │
                                  └─────────────┘
```

- **`pi/`** — runs on the Raspberry Pi that's physically attached to the
  vault. Denies access outside a configured time window or if a fingerprint
  (R307 sensor) and face scan (Pi Camera) don't both match the enrolled
  owner. Drives the lock relay, siren, and status LEDs directly over GPIO.
  Every attempt — granted or denied — is POSTed to the backend as an event.
- **`backend/`** — Express API backed by Postgres. Stores every event,
  computes a canonical `keccak256` hash of it, and anchors that hash
  on-chain (via `contracts/Vault.sol`) whenever `tamper: true`. Also holds
  basic user registration/login (bcrypt + JWT) for the dashboard.
- **`contracts/`** — a minimal Solidity contract (Foundry project) that
  stores `(hash, deviceTimestamp, blockTimestamp, lat, lng)` per event.
  Only the backend's wallet (the contract `owner`) can write; anyone can
  call `verify()` to check a hash against what's on-chain. This is what
  makes the ledger tamper-evident — the backend's Postgres row can be
  edited, but the on-chain anchor can't, so `GET /events/:id/verify` catches
  the mismatch.
- **`frontend/`** — a single-file dashboard (`index.html`, no build step)
  that shows box status, the live event ledger, an integrity-verify action
  per event, and Etherscan links for anchored events. Falls back to a demo
  mode if the backend is unreachable.

Each subfolder has its own README with full setup detail; this one is the
map of how they talk to each other and the fastest path to a working demo.

## Quick start (backend + frontend only, no hardware)

This is enough to see the dashboard and ledger working; it skips the Pi and
the on-chain anchor (anchoring is skipped automatically if `CONTRACT_ADDRESS`
isn't set — events still get hashed and stored off-chain).

1. **Postgres** — have a database ready and its connection string handy.
2. **Backend**
   ```bash
   cd backend
   npm install
   ```
   Create `backend/.env` (there's no `.env.example` committed yet, so start
   one — see [Backend environment variables](#backend-environment-variables)
   below for every key it reads):
   ```bash
   PORT=3000
   DATABASE_URL=postgres://user:pass@localhost:5432/vault
   INGEST_API_KEY=some-long-random-string
   JWT_SECRET=some-other-long-random-string
   ```
   ```bash
   npm start
   ```
   Should print `DB ready` then `backend on :3000 (...)`.
3. **Frontend** — open `frontend/index.html` directly in a browser. It talks
   to `http://localhost:3000` by default (edit the `API` const at the top of
   the file to change that). To use the "Simulate tamper" button against a
   real backend, set `API_KEY` in `index.html` to match `INGEST_API_KEY`
   above.

### Backend environment variables

| Variable | Required | Purpose |
|---|---|---|
| `PORT` | no (default `3000`) | HTTP port the API listens on |
| `DATABASE_URL` | yes | Postgres connection string |
| `INGEST_API_KEY` | yes | Shared secret events must send as `x-api-key`; must match `pi/.env`'s `INGEST_API_KEY` and, for the demo button, `index.html`'s `API_KEY` |
| `JWT_SECRET` | yes | Signing secret for `users/register` and `users/login` tokens |
| `RPC_URL` | only for on-chain anchoring | Ethereum RPC endpoint (e.g. a Sepolia RPC) |
| `PRIVATE_KEY` | only for on-chain anchoring | Private key of the wallet that owns the deployed `Vault` contract |
| `CONTRACT_ADDRESS` | only for on-chain anchoring | Deployed `Vault.sol` address. If unset, tamper events are hashed and stored, just never anchored |

## Full setup (with hardware + on-chain anchoring)

1. **Deploy the contract** — see `contracts/README.md` for Foundry basics
   (`forge build`, `forge test`, deploy with `forge script`/`cast`). Note the
   deployed address.
2. **Backend** — set `RPC_URL`, `PRIVATE_KEY` (must be the contract's
   `owner`), and `CONTRACT_ADDRESS` in `backend/.env`, then start as above.
   Tamper events will now anchor on-chain automatically; check the backend
   logs for `anchored on-chain (tx ...)`.
3. **Pi** — see `pi/README.md` for wiring, enrollment, and running as a
   systemd service. Its `.env` needs `BACKEND_URL` pointing at the backend
   above and a matching `INGEST_API_KEY`.
4. **Frontend** — point `API` in `index.html` at the backend's real address
   if it's not on `localhost:3000`.

## Data flow / how tamper-evidence works

1. The Pi (or any device using the same event shape) POSTs an event to
   `backend/routes/events.js`.
2. The backend computes `hashEvent()` — a stable `keccak256` hash over the
   event's sorted-key JSON — and stores the event plus its hash in Postgres.
3. If `tamper: true`, the backend calls `Vault.logEvent()` on-chain with
   that hash, the device timestamp, and lat/lng (scaled ×1e6, since Solidity
   has no floats). The transaction hash and on-chain record id are saved
   back onto the Postgres row.
4. `GET /events/:id/verify` recomputes the hash from the stored row and
   compares it against both the stored hash (`dbMatch`) and, if anchored,
   the on-chain record (`chainMatch`) via `Vault.verify()`. If someone edits
   a row directly in Postgres, `dbMatch` (and for tamper events, `chainMatch`)
   will fail — that mismatch is the tamper signal the dashboard surfaces.

## Repo layout

```
backend/     Express API + Postgres storage + on-chain anchoring
contracts/   Vault.sol (Foundry project) — the on-chain hash ledger
frontend/    Single-file dashboard (index.html)
pi/          Raspberry Pi access-control service (fingerprint + face + lock)
```

## Notes

- The Pi is the source of truth for the access decision (time window +
  identity) and works even if the backend is unreachable — logging to the
  backend is fire-and-forget so a slow network never delays the physical
  lock/siren response.
- Only `tamper: true` events are anchored on-chain today; routine
  status/checkpoint events are hashed and stored off-chain only.
- `backend/postman/anti-tamper-vault.postman_collection.json` has ready-made
  requests for the API if you want to poke it without the Pi or frontend.

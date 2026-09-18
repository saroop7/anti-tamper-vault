# Frontend Dashboard

Single file: `index.html`. Open it in any browser — no build step.

- Talks to the backend at `http://localhost:3000` (matches `PORT` in `backend/.env`;
  edit the `API` const to change).
- "Simulate tamper" needs `API_KEY` in `index.html` to match `INGEST_API_KEY` in
  `backend/.env` (defaults to the local dev key already used by `scripts/fake-sensor.js`)
  — it's a demo-only key, never put a real production key in client-side code.
- If the backend is unreachable it drops into **demo mode** so you can rehearse
  visuals anytime — the "Simulate tamper" button still builds a visible ledger entry.
- Shows: box status card, live event ledger, "Verify integrity" (recomputes each
  event's hash via `GET /events/:id/verify` and flags any mismatch), Etherscan links
  for anchored events.

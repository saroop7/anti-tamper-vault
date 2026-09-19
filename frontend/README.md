# Frontend Dashboard

React + Vite, built to plain static files — deployment doesn't change even
though the source does.

```bash
npm install       # once
npm run dev       # local dev server with hot reload, http://localhost:5173
npm run build     # writes static index.html/register.html + assets to dist/
```

After `npm run build`, serve `dist/` exactly like the old static HTML was
served (e.g. `python3 -m http.server` from inside `dist/`, or the existing
Tailscale setup) — there's no Node server involved at runtime, only at build
time.

- Talks to the backend over Tailscale (`src/lib/api.js`'s `API` const) —
  edit that to change it.
- If the backend is unreachable, the connection dot goes amber/"offline" and
  the ledger just shows no records rather than fabricating demo data.
- Two pages, two Vite entry points: `index.html` (Box Monitor — status card,
  live event ledger, "Verify integrity", reverse-geocoded tamper locations,
  Etherscan links for anchored events) and `register.html` (User
  Registrations — PIN-gated user list and the "Add new user" enrollment
  flow that talks to the Pi via the backend's enrollment-request queue).
- Source layout: `src/pages/` (one component per page), `src/components/`
  (shared UI), `src/lib/` (API client, theme cycling, reverse-geocoding
  cache/queue, date/hash formatting), `src/icons.jsx` (monochrome SVG icon
  set, no color emoji).
- Theme cycles light → dark → disco (a slow, safe black/white crossfade,
  capped well under the seizure-risk flash threshold and disabled under
  `prefers-reduced-motion`) via the toggle button, persisted to
  `localStorage`.

// Tailscale MagicDNS hostname -- stable regardless of which WiFi this page
// (or the backend's Mac) is on, so this never needs updating when the LAN
// IP changes. Requires the viewing device to also be on the same Tailnet.
export const API = "http://saroops-macbook-air.tailb523e7.ts.net:3000";

export async function apiFetch(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

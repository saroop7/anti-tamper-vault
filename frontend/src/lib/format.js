// full hash is always shown in the ledger -- nothing truncated
export function fullHash(h) {
  return h || "—";
}

// display-only: server stores/hashes timestamps in UTC, we just render them in IST here
const istFormatter = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
});

export function formatIST(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  return istFormatter.format(d) + " IST";
}

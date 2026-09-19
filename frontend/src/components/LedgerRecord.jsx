import { hasGeo, useGeoLabel } from "../lib/geocode";
import { formatIST, fullHash } from "../lib/format";

export default function LedgerRecord({ record: r, verifyResult: v, index = 0 }) {
  const failed = v && (v.dbMatch === false || v.chainMatch === false);
  const checked = v && !failed;
  const geo = hasGeo(r.lat, r.lng);
  // hooks run unconditionally regardless of hasGeo; the hook itself no-ops
  // (returns null, does no fetch) when lat/lng aren't present
  const geoLabel = useGeoLabel(r.lat, r.lng);

  return (
    <li
      className={"link" + (r.tamper ? " tamper" : "") + (failed ? " fail" : "")}
      style={{ "--i": Math.min(index, 8) }}
    >
      <div className="link-top">
        <span className="etype">
          {r.event_type}
          <span className={"tag " + (r.tamper ? "tamper" : "bump")}>{r.tamper ? "TAMPER" : "normal"}</span>
          {r.enrolledUser ? <span className="tag enroll">ENROLLMENT</span> : null}
          {failed ? <span className="tag fail">VERIFY FAILED</span> : null}
          {checked ? <span className="tag ok">VERIFIED</span> : null}
        </span>
        <span className="time">{formatIST(r.timestamp)}</span>
      </div>
      <div className="hash-row">
        <div className="hash-block">
          <span className="hash-label">SHA-256 hash</span>
          <span className="hash-value">{fullHash(r.hash)}</span>
        </div>
        <span className={"anchor " + r.anchor}>
          {r.anchor === "on_chain" ? (
            r.onchain_tx ? (
              <a href={`https://sepolia.etherscan.io/tx/${r.onchain_tx}`} target="_blank" rel="noreferrer">
                on-chain ↗
              </a>
            ) : (
              "on-chain"
            )
          ) : (
            "off-chain"
          )}
        </span>
      </div>
      {/* who got enrolled is deliberately NOT shown here -- see the PIN-gated
          "User registrations" page instead. The ledger only flags that an
          enrollment happened, not whose. */}
      {geo ? (
        <div className="geo-row">
          <span className="hash-label">Location</span>
          <span className="geo-value">{geoLabel || "Locating…"}</span>
          <a href={`https://maps.google.com/?q=${r.lat},${r.lng}`} target="_blank" rel="noreferrer">
            map ↗
          </a>
        </div>
      ) : null}
    </li>
  );
}

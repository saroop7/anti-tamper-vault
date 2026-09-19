import { useCallback, useEffect, useRef, useState } from "react";
import { API, apiFetch } from "../lib/api";
import { useLiveUpdates } from "../lib/liveUpdates";
import NavMenu from "../components/NavMenu";
import ConnDot from "../components/ConnDot";
import LedgerRecord from "../components/LedgerRecord";
import BackgroundMusic from "../components/BackgroundMusic";
import { CheckIcon, AlertIcon } from "../icons";

// backend (GET /events) returns DB rows newest-first already
function normalise(rows) {
  return rows.map((r) => ({
    id: r.id,
    device_id: r.device_id,
    event_type: r.status,
    timestamp: r.device_ts,
    hash: r.data_hash,
    onchain_tx: r.onchain_tx,
    anchor: r.onchain_tx ? "on_chain" : "off_chain",
    tamper: !!r.tamper,
    lat: r.lat,
    lng: r.lng,
    locationOnChain: !!r.location_onchain,
    enrolledUser: r.status === "user_registered" ? r.sensor_data && r.sensor_data.name : null,
    biometricSlot: r.status === "user_registered" ? r.sensor_data && r.sensor_data.fingerprint_slot : null,
  }));
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "tamper", label: "Tamper" },
  { key: "unlocked", label: "Unlocked" },
  { key: "offchain", label: "Off-chain" },
];

const EMPTY_MESSAGE = {
  all: "No events yet. Trigger one to see the ledger build.",
  tamper: "No tamper events match this filter.",
  unlocked: "No unlock events match this filter.",
  offchain: "No off-chain records match this filter.",
};

function applyFilter(records, mode) {
  if (mode === "tamper") return records.filter((r) => r.tamper);
  if (mode === "unlocked") return records.filter((r) => r.event_type === "UNLOCKED");
  if (mode === "offchain") return records.filter((r) => r.anchor === "off_chain");
  return records;
}

export default function BoxMonitor() {
  const [records, setRecords] = useState([]);
  const [live, setLive] = useState(null);
  const [filterMode, setFilterMode] = useState("all");
  const [verifyResults, setVerifyResults] = useState(new Map());
  const [verdict, setVerdict] = useState(null); // { cls, text }
  const verifyingRef = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const rows = await apiFetch("/events");
      setLive(true);
      setRecords(normalise(rows));
    } catch (e) {
      setLive(false);
      setRecords([]); // no live backend, no local data to fall back to
    }
  }, []);

  useEffect(() => {
    refresh();
    // 60s is just the fallback in case the push connection below ever
    // drops silently -- the SSE subscription is what makes this feel instant
    const id = setInterval(refresh, 60000);
    return () => clearInterval(id);
  }, [refresh]);

  // push-driven refresh: the backend broadcasts on /stream the instant a
  // new event lands, so this updates immediately instead of waiting for
  // the next poll tick
  useLiveUpdates(
    useCallback(
      (type) => {
        if (type === "events") refresh();
      },
      [refresh]
    )
  );

  const verifyChain = useCallback(async () => {
    if (verifyingRef.current) return;
    verifyingRef.current = true;
    try {
      const rows = await apiFetch("/events");
      const recs = normalise(rows).slice(0, 25); // most recent 25, keeps this snappy
      setVerdict({ cls: "", text: `Verifying ${recs.length} record(s)…` });
      const results = await Promise.all(recs.map((r) => apiFetch(`/events/${r.id}/verify`)));
      setVerifyResults(new Map(results.map((res) => [res.id, res])));
      setRecords(recs);
      const failedOnes = results.filter((res) => res.dbMatch === false || res.chainMatch === false);
      if (failedOnes.length === 0) {
        setVerdict({ cls: "ok", text: `✓ ${recs.length} record(s) verified — recomputed hashes match, no tampering detected.` });
      } else {
        setVerdict({ cls: "bad", text: `✗ Verification FAILED on record #${failedOnes.map((f) => f.id).join(", #")}.` });
      }
    } catch (e) {
      setVerdict({ cls: "bad", text: "✗ Couldn't reach the backend to verify." });
    } finally {
      verifyingRef.current = false;
    }
  }, []);

  const filtered = applyFilter(records, filterMode);
  const secure = !(records.length && records[0].tamper);
  const boxId = records[0]?.device_id || "BOX-001";

  return (
    <div className="page page-monitor">
      <header>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <NavMenu navLink={{ href: "register.html", label: "User registrations →" }} />
          <h1>
            Custody Chain <span>/ Box Monitor</span>
          </h1>
        </div>
        <ConnDot live={live} />
      </header>

      <main>
        <section className="status">
          <div>
            <div className="box-id">{boxId}</div>
            <div className={"state " + (secure ? "secure" : "tampered")}>{secure ? "SECURE" : "TAMPERED"}</div>
          </div>
          <div className={"seal " + (secure ? "secure" : "tampered")}>{secure ? <CheckIcon /> : <AlertIcon />}</div>
        </section>

        <div className="controls">
          <button className="primary" onClick={verifyChain}>
            Verify integrity
          </button>
          <button onClick={refresh}>Refresh</button>
        </div>
        <div key={verdict?.text || ""} className={"verdict " + (verdict?.cls || "")}>
          {verdict?.text || ""}
        </div>

        <h2>Event ledger — newest first</h2>
        <div className="filters" role="group" aria-label="Ledger filter">
          <span className="flabel">Filter</span>
          <div className="segmented">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                className={"filter-btn" + (filterMode === f.key ? " active" : "")}
                onClick={() => setFilterMode(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* keyed by filterMode so switching filters replays the entrance
            animation for the newly-visible set (a deliberate crossfade),
            while a same-filter poll refresh keeps each row's DOM node
            stable and only animates genuinely new records in */}
        <ul className="chain" key={filterMode}>
          {records.length === 0 ? (
            <li className="empty">{EMPTY_MESSAGE.all}</li>
          ) : filtered.length === 0 ? (
            <li className="empty">{EMPTY_MESSAGE[filterMode]}</li>
          ) : (
            filtered.map((r, i) => (
              <LedgerRecord key={r.id} record={r} verifyResult={verifyResults.get(r.id)} index={i} />
            ))
          )}
        </ul>

        <footer>
          Reading from backend at <span>{API}</span>
        </footer>
      </main>

      <BackgroundMusic />
    </div>
  );
}

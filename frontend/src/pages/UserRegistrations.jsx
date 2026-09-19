import { useCallback, useEffect, useRef, useState } from "react";
import { API, apiFetch } from "../lib/api";
import { useLiveUpdates } from "../lib/liveUpdates";
import NavMenu from "../components/NavMenu";
import ConnDot from "../components/ConnDot";
import { LockIcon, PersonIcon } from "../icons";
import { formatIST } from "../lib/format";

// Client-side speed bump for a casual glance at the screen, not real access
// control -- anyone reading the page source sees it.
const PANEL_PIN = "1290";

function BlueTintFilter() {
  // undoes the red/blue channel swap in already-stored enrollment photos --
  // exact swap, not a hue approximation, so skin tones come back correct
  return (
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <filter id="fix-blue-tint" colorInterpolationFilters="sRGB">
        <feColorMatrix type="matrix" values="0 0 1 0 0  0 1 0 0 0  1 0 0 0 0  0 0 0 1 0" />
      </filter>
    </svg>
  );
}

function Avatar({ user }) {
  const hasFace = user.face_id && user.face_id !== "no_image_captured";
  if (!hasFace) {
    return (
      <div className="avatar">
        <PersonIcon />
      </div>
    );
  }
  // the Pi's camera stores enrollment photos upside down and with red/blue
  // swapped -- both fixed at display time via img.avatar's CSS (transform +
  // #fix-blue-tint filter); the capture-side fix lives in pi/enrollment_logic.py
  return <img className="avatar" src={`data:image/jpeg;base64,${user.face_id}`} alt={user.name} />;
}

const PIN_LENGTH = 4;

export default function UserRegistrations() {
  const [unlocked, setUnlocked] = useState(false);
  const [digits, setDigits] = useState(Array(PIN_LENGTH).fill(""));
  const [pinError, setPinError] = useState("");
  const [shake, setShake] = useState(false);
  const [users, setUsers] = useState([]);
  const [live, setLive] = useState(null);
  const [gridMessage, setGridMessage] = useState("Loading registrations…");
  const [newName, setNewName] = useState("");
  const [addDisabled, setAddDisabled] = useState(false);
  const [reqStatus, setReqStatus] = useState(null); // { kind: wait|ok|bad, text }
  const [showStop, setShowStop] = useState(false);

  const currentRequestId = useRef(null);
  const statusPollTimer = useRef(null);
  const refreshTimer = useRef(null);
  const digitRefs = useRef([]);

  useEffect(() => {
    if (!unlocked) digitRefs.current[0]?.focus();
  }, [unlocked]);

  const load = useCallback(async () => {
    try {
      const rows = await apiFetch("/enrollments");
      setLive(true);
      setUsers(rows);
      if (!rows.length) setGridMessage("No users registered yet. Enroll one from the vault hardware.");
    } catch (e) {
      setLive(false);
      setUsers([]);
      setGridMessage("Can't reach the backend right now.");
    }
  }, []);

  useEffect(() => {
    if (!unlocked) return;
    load();
    // 8s is just the fallback in case the push connection below ever
    // drops silently -- the SSE subscription is what makes this feel instant
    refreshTimer.current = setInterval(load, 8000);
    return () => {
      clearInterval(refreshTimer.current);
      refreshTimer.current = null;
    };
  }, [unlocked, load]);

  // push-driven refresh: the backend broadcasts on /stream the instant a
  // new enrollment lands, so the list updates immediately instead of
  // waiting for the next poll tick -- only acts while the panel is unlocked
  useLiveUpdates(
    useCallback(
      (type) => {
        if (type === "enrollments" && unlocked) load();
      },
      [unlocked, load]
    )
  );

  function resetDigits() {
    setDigits(Array(PIN_LENGTH).fill(""));
    digitRefs.current[0]?.focus();
  }

  function tryUnlock(candidate) {
    if (candidate === PANEL_PIN) {
      setUnlocked(true);
      setPinError("");
      setDigits(Array(PIN_LENGTH).fill(""));
    } else {
      setPinError("Wrong PIN");
      setShake(true);
      setTimeout(() => setShake(false), 400);
      resetDigits();
    }
  }

  function handleDigitChange(i, raw) {
    const value = raw.replace(/\D/g, "").slice(-1); // last typed digit only, numeric
    setPinError("");
    const next = [...digits];
    next[i] = value;
    setDigits(next);

    if (value && i < PIN_LENGTH - 1) {
      digitRefs.current[i + 1]?.focus();
    }
    if (value && i === PIN_LENGTH - 1 && next.every((d) => d !== "")) {
      tryUnlock(next.join(""));
    }
  }

  function handleDigitKeyDown(i, e) {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      digitRefs.current[i - 1]?.focus();
    }
    if (e.key === "Enter") {
      tryUnlock(digits.join(""));
    }
  }

  function handlePinPaste(e) {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, PIN_LENGTH);
    if (!pasted) return;
    e.preventDefault();
    const next = Array(PIN_LENGTH).fill("");
    for (let i = 0; i < pasted.length; i++) next[i] = pasted[i];
    setDigits(next);
    if (pasted.length === PIN_LENGTH) tryUnlock(pasted);
    else digitRefs.current[pasted.length]?.focus();
  }

  function lockPanel() {
    setUnlocked(false);
  }

  function stopPolling() {
    if (statusPollTimer.current) clearInterval(statusPollTimer.current);
    statusPollTimer.current = null;
  }

  const pollRequestStatus = useCallback(
    (id, name) => {
      stopPolling();
      statusPollTimer.current = setInterval(async () => {
        try {
          const rows = await apiFetch("/enrollment-requests");
          const req = rows.find((r) => r.id === id);
          if (!req) return;

          if (req.status === "in_progress") {
            setReqStatus({ kind: "wait", text: `Enrolling "${name}" now — follow the prompts on the vault's display…` });
          } else if (req.status === "done") {
            setReqStatus({ kind: "ok", text: `✓ "${name}" enrolled successfully.` });
            stopPolling();
            setShowStop(false);
            setAddDisabled(false);
            currentRequestId.current = null;
            load();
          } else if (req.status === "failed") {
            setReqStatus({ kind: "bad", text: `✗ Enrollment failed: ${req.error || "unknown error"}` });
            stopPolling();
            setShowStop(false);
            setAddDisabled(false);
            currentRequestId.current = null;
          } else if (req.status === "cancelled") {
            stopPolling();
            setShowStop(false);
            setAddDisabled(false);
            currentRequestId.current = null;
          }
        } catch (e) {
          // transient network hiccup -- keep polling, don't give up on one failed check
        }
      }, 2000);
    },
    [load]
  );

  async function requestEnrollment() {
    const name = newName.trim();
    if (!name) return;

    setAddDisabled(true);
    try {
      const request = await apiFetch("/enrollment-requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      setNewName("");
      currentRequestId.current = request.id;
      setReqStatus({ kind: "wait", text: `Queued — waiting for the Pi to enroll "${name}" (place finger + look at camera when it starts)…` });
      setShowStop(true);
      pollRequestStatus(request.id, name);
    } catch (e) {
      setReqStatus({ kind: "bad", text: "✗ Couldn't queue the request — backend unreachable." });
      setAddDisabled(false);
    }
  }

  async function stopEnrollment() {
    if (!currentRequestId.current) return;
    setShowStop(false);
    try {
      await fetch(`${API}/enrollment-requests/${currentRequestId.current}/cancel`, { method: "POST" });
      setReqStatus({ kind: "bad", text: "✗ Enrollment stopped." });
    } catch (e) {
      setReqStatus({ kind: "bad", text: "✗ Couldn't reach the backend to stop it — it may still be running." });
    } finally {
      stopPolling();
      setAddDisabled(false);
      currentRequestId.current = null;
    }
  }

  useEffect(() => stopPolling, []); // clear any pending timer on unmount

  return (
    <div className="page page-register">
      <BlueTintFilter />
      <header>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <NavMenu navLink={{ href: "index.html", label: "← Box Monitor" }} />
          <h1>
            User Registrations <span>/ Custody Chain</span>
          </h1>
        </div>
        <ConnDot live={unlocked ? live : null} />
      </header>

      <main>
        {!unlocked ? (
          <div className="pin-gate">
            <div className="pin-badge">
              <LockIcon />
            </div>
            <h2 className="pin-title">Enter Password</h2>
            <p className="pin-subtitle">This panel is protected — enter the 4-digit PIN to continue.</p>

            <div className={"pin-digits" + (shake ? " shake" : "")} onPaste={handlePinPaste}>
              {digits.map((d, i) => (
                <input
                  key={i}
                  ref={(el) => (digitRefs.current[i] = el)}
                  className="pin-digit"
                  type="password"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={1}
                  autoComplete="off"
                  value={d}
                  onChange={(e) => handleDigitChange(i, e.target.value)}
                  onKeyDown={(e) => handleDigitKeyDown(i, e)}
                />
              ))}
            </div>

            {pinError ? <div className="pin-error">{pinError}</div> : null}

            <button className="primary pin-submit" onClick={() => tryUnlock(digits.join(""))}>
              Unlock
            </button>
          </div>
        ) : (
          <div>
            <div className="lock-toolbar">
              <button onClick={lockPanel}>Hide again</button>
            </div>

            <div className="add-panel">
              <input
                type="text"
                placeholder="Name to enroll (e.g. Nikhil)"
                maxLength={80}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <button className="primary" disabled={addDisabled} onClick={requestEnrollment}>
                Add new user →
              </button>
            </div>
            {reqStatus ? (
              <div key={reqStatus.text} className={"req-status " + reqStatus.kind}>
                {reqStatus.kind === "wait" ? <span className="spin"></span> : null}
                {reqStatus.text}
              </div>
            ) : null}
            {showStop ? (
              <button
                onClick={stopEnrollment}
                style={{ display: "inline-block", marginTop: 10, borderColor: "var(--tamper)", color: "var(--tamper)" }}
              >
                Stop enrollment
              </button>
            ) : null}

            <div className="toolbar">
              <span style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--muted)" }}>
                {users.length} registered
              </span>
              <button onClick={load}>Refresh</button>
            </div>

            <div className="grid">
              {users.length === 0 ? (
                <div className="empty">{gridMessage}</div>
              ) : (
                users.map((u) => (
                  <div className="card" key={u.id}>
                    <Avatar user={u} />
                    <div className="card-body">
                      <div className="card-name">{u.name}</div>
                      <div className="card-meta">
                        <span>fingerprint slot {u.fingerprint_slot}</span>
                        <span>enrolled {formatIST(u.enrolled_at)}</span>
                        {u.firmware_ver ? <span>fw {u.firmware_ver}</span> : null}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

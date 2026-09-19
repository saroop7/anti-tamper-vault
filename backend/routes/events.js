import { Router } from "express";
import { pool } from "../db.js";
import { hashEvent, anchorHash, verifyOnChain } from "../anchor.js";
import { broadcast } from "../sse.js";

export const router = Router();

// display-only: logs in IST, storage/hashing still use the raw UTC device_ts
const istFormatter = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true,
});
function formatIST(date) {
  return istFormatter.format(date) + " IST";
}

// Simple API-key gate so nobody can spoof a tamper=false reading.
function requireKey(req, res, next) {
  if (req.header("x-api-key") !== process.env.INGEST_API_KEY) {
    return res.status(401).json({ error: "bad api key" });
  }
  next();
}

// POST /events — hardware sends readings here
router.post("/", requireKey, async (req, res) => {
  const { device_id, device_ts, status, tamper, sensor_data, lat, lng } = req.body;
  if (!device_id || !device_ts || !status || typeof tamper !== "boolean") {
    return res.status(400).json({ error: "missing/invalid fields" });
  }
  if (lat !== undefined && typeof lat !== "number") {
    return res.status(400).json({ error: "lat must be a number" });
  }
  if (lng !== undefined && typeof lng !== "number") {
    return res.status(400).json({ error: "lng must be a number" });
  }

  const evt = { device_id, device_ts, status, tamper, sensor_data, lat: lat ?? null, lng: lng ?? null };
  const dataHash = hashEvent(evt);

  const insert = await pool.query(
    `INSERT INTO events (device_id, device_ts, status, tamper, sensor_data, lat, lng, data_hash)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id`,
    [device_id, device_ts, status, tamper, sensor_data ?? null, lat ?? null, lng ?? null, dataHash]
  );
  const id = insert.rows[0].id;
  console.log(`[${formatIST(new Date())}] event #${id} received (${status}${tamper ? ", TAMPER" : ""})`);
  broadcast("events"); // wake up any dashboards watching /stream

  // Anchor only tamper events (checkpoints can be added later).
  if (tamper) {
    try {
      const tsSeconds = Math.floor(new Date(device_ts).getTime() / 1000);
      const result = await anchorHash(dataHash, tsSeconds, lat, lng);
      if (result) {
        await pool.query(
          `UPDATE events SET onchain_tx=$1, onchain_id=$2, onchain_contract=$3 WHERE id=$4`,
          [result.txHash, result.onchainId, result.contract, id]
        );
        console.log(`[${formatIST(new Date())}] event #${id} anchored on-chain (tx ${result.txHash})`);
        broadcast("events"); // the onchain_tx/anchor badge just changed too
      }
    } catch (e) {
      console.error(`[${formatIST(new Date())}] anchor failed:`, e.message); // event still saved off-chain
    }
  }

  res.status(201).json({ id, data_hash: dataHash });
});

// GET /events — full history for the dashboard timeline
router.get("/", async (_req, res) => {
  const { rows } = await pool.query(`SELECT * FROM events ORDER BY id DESC`);
  const current = (process.env.CONTRACT_ADDRESS || "").toLowerCase();
  // location_onchain is only true when this row was anchored to the *current*
  // contract -- earlier rows may have been anchored to a prior contract
  // address that didn't have lat/lng fields at all, so their location (even
  // if present) only ever lived off-chain in this table.
  res.json(rows.map(r => ({
    ...r,
    location_onchain: !!(r.onchain_contract && r.onchain_contract.toLowerCase() === current),
  })));
});

// GET /events/:id/verify — recompute hash, check DB + chain agree
router.get("/:id/verify", async (req, res) => {
  const { rows } = await pool.query(`SELECT * FROM events WHERE id=$1`, [req.params.id]);
  if (rows.length === 0) return res.status(404).json({ error: "not found" });
  const row = rows[0];

  const recomputed = hashEvent({
    device_id: row.device_id,
    device_ts: row.device_ts.toISOString(),
    status: row.status,
    tamper: row.tamper,
    sensor_data: row.sensor_data,
    lat: row.lat,
    lng: row.lng,
  });

  const dbMatch = recomputed === row.data_hash;
  let chainMatch = null;
  if (row.onchain_id !== null) {
    chainMatch = await verifyOnChain(row.onchain_id, row.data_hash);
  }

  res.json({ id: row.id, dbMatch, chainMatch, stored: row.data_hash, recomputed });
});
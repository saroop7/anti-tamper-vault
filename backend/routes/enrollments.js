import { Router } from "express";
import { pool } from "../db.js";

export const router = Router();

// Same API-key gate as /events -- the Pi's enrollment device is the only
// thing allowed to write here.
function requireKey(req, res, next) {
  if (req.header("x-api-key") !== process.env.INGEST_API_KEY) {
    return res.status(401).json({ error: "bad api key" });
  }
  next();
}

// POST /enrollments — hardware sends a completed biometric enrollment here
router.post("/", requireKey, async (req, res) => {
  const { device_id, name, fingerprint_slot, face_id, firmware_ver } = req.body;
  if (!device_id || !name || typeof fingerprint_slot !== "number") {
    return res.status(400).json({ error: "missing/invalid fields" });
  }

  const insert = await pool.query(
    `INSERT INTO enrollments (device_id, name, fingerprint_slot, face_id, firmware_ver)
     VALUES ($1,$2,$3,$4,$5) RETURNING id, enrolled_at`,
    [device_id, name, fingerprint_slot, face_id ?? null, firmware_ver ?? null]
  );

  // req.ip is the caller's source address -- a Tailscale-routed request
  // shows up as 100.x.x.x, so this line doubles as a live "did it really
  // come over Tailscale" check when you're watching the terminal.
  console.log(`[enrollments] #${insert.rows[0].id} "${name}" enrolled from ${device_id} (source ${req.ip})`);

  res.status(201).json(insert.rows[0]);
});

// GET /enrollments — full list for the frontend's registration page
router.get("/", async (_req, res) => {
  const { rows } = await pool.query(`SELECT * FROM enrollments ORDER BY id DESC`);
  res.json(rows);
});

import { Router } from "express";
import { pool } from "../db.js";

export const router = Router();

function requireKey(req, res, next) {
  if (req.header("x-api-key") !== process.env.INGEST_API_KEY) {
    return res.status(401).json({ error: "bad api key" });
  }
  next();
}

// POST /enrollment-requests — frontend queues a name to enroll
router.post("/", async (req, res) => {
  const { name } = req.body;
  if (!name || typeof name !== "string" || !name.trim()) {
    return res.status(400).json({ error: "name is required" });
  }
  const insert = await pool.query(
    `INSERT INTO enrollment_requests (name) VALUES ($1) RETURNING *`,
    [name.trim()]
  );
  console.log(`[enrollment_requests] queued "${name.trim()}" (source ${req.ip})`);
  res.status(201).json(insert.rows[0]);
});

// GET /enrollment-requests — full list, newest first (frontend status view)
router.get("/", async (_req, res) => {
  const { rows } = await pool.query(`SELECT * FROM enrollment_requests ORDER BY id DESC LIMIT 50`);
  res.json(rows);
});

// POST /enrollment-requests/:id/cancel — frontend "stop" button. Only
// works while the request hasn't finished yet; the Pi worker checks this
// status mid-capture and aborts as soon as it notices.
router.post("/:id/cancel", async (req, res) => {
  const { rows } = await pool.query(
    `UPDATE enrollment_requests SET status='cancelled', updated_at=now()
     WHERE id=$1 AND status IN ('pending','in_progress') RETURNING *`,
    [req.params.id]
  );
  if (rows.length === 0) {
    return res.status(409).json({ error: "already finished or not found" });
  }
  console.log(`[enrollment_requests] #${req.params.id} cancelled`);
  res.json(rows[0]);
});

// GET /enrollment-requests/:id/status — cheap poll target for the Pi to
// check mid-capture whether the frontend hit "stop", without pulling the
// whole list on every check.
router.get("/:id/status", requireKey, async (req, res) => {
  const { rows } = await pool.query(`SELECT status FROM enrollment_requests WHERE id=$1`, [req.params.id]);
  if (rows.length === 0) return res.status(404).json({ error: "not found" });
  res.json(rows[0]);
});

// GET /enrollment-requests/pending — the Pi polls this for its next job.
// Only ever returns the single oldest pending request, never a batch --
// the daemon handles one enrollment at a time (one fingerprint sensor).
router.get("/pending", requireKey, async (_req, res) => {
  const { rows } = await pool.query(
    `SELECT * FROM enrollment_requests WHERE status = 'pending' ORDER BY id ASC LIMIT 1`
  );
  res.json(rows[0] || null);
});

// POST /enrollment-requests/:id/status — the Pi reports progress/result
router.post("/:id/status", requireKey, async (req, res) => {
  const { status, error, enrollment_id } = req.body;
  if (!["in_progress", "done", "failed"].includes(status)) {
    return res.status(400).json({ error: "invalid status" });
  }
  const { rows } = await pool.query(
    `UPDATE enrollment_requests
     SET status=$1, error=$2, enrollment_id=$3, updated_at=now()
     WHERE id=$4 RETURNING *`,
    [status, error ?? null, enrollment_id ?? null, req.params.id]
  );
  if (rows.length === 0) return res.status(404).json({ error: "not found" });
  console.log(`[enrollment_requests] #${req.params.id} -> ${status}`);
  res.json(rows[0]);
});

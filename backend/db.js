import pg from "pg";
import dotenv from "dotenv";
dotenv.config();

const { Pool } = pg;
export const pool = new Pool({ connectionString: process.env.DATABASE_URL });
// Without this, an idle client dropped by Postgres (restart, network blip)
// fires an unhandled 'error' event and crashes the whole process.
pool.on("error", (err) => console.error("idle client error:", err.message));

// Creates the table on first run. Safe to call every startup.
export async function initDb() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS events (
      id           SERIAL PRIMARY KEY,
      device_id    TEXT        NOT NULL,
      device_ts    TIMESTAMPTZ NOT NULL,
      status       TEXT        NOT NULL,
      tamper       BOOLEAN     NOT NULL,
      sensor_data  JSONB,
      lat          DOUBLE PRECISION,
      lng          DOUBLE PRECISION,
      data_hash    TEXT        NOT NULL,
      onchain_tx   TEXT,
      onchain_id   INTEGER,
      created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  `);
  // Backfill columns for databases created before GPS support was added.
  await pool.query(`ALTER TABLE events ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;`);
  await pool.query(`ALTER TABLE events ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION;`);
  // Which Vault contract address a given anchor was written to -- the contract
  // gets redeployed occasionally (e.g. to add new on-chain fields), and older
  // rows anchored to a prior address may not have every field the current
  // contract supports. Recorded per-row so we never assume an old anchor has
  // data the contract it actually used didn't store.
  await pool.query(`ALTER TABLE events ADD COLUMN IF NOT EXISTS onchain_contract TEXT;`);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      id            SERIAL PRIMARY KEY,
      email         TEXT        NOT NULL UNIQUE,
      password_hash TEXT        NOT NULL,
      created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  `);

  console.log("DB ready");
}
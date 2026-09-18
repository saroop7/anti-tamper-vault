import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { initDb } from "../db.js";
import { router as eventsRouter } from "../routes/events.js";
import { router as usersRouter } from "../routes/users.js";
dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());
app.use("/events", eventsRouter);
app.use("/users", usersRouter);
app.get("/health", (_req, res) => res.json({ ok: true }));

const PORT = process.env.PORT || 3000;
const istFormatter = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true,
});

initDb()
  .then(() => {
    app.listen(PORT, () =>
      console.log(`backend on :${PORT} (started ${istFormatter.format(new Date())} IST)`)
    );
  })
  .catch((err) => {
    console.error("startup failed:", err);
    process.exit(1);
  });
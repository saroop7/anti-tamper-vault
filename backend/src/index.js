import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { initDb } from "../db.js";
import { router as eventsRouter } from "../routes/events.js";
import { router as usersRouter } from "../routes/users.js";
import { router as enrollmentsRouter } from "../routes/enrollments.js";
import { router as enrollmentRequestsRouter } from "../routes/enrollmentRequests.js";
dotenv.config();

const app = express();
app.use(cors());
// Raised from the 100kb default -- enrollment payloads carry a base64 JPEG
// face capture, which a small default limit would reject with 413.
app.use(express.json({ limit: "5mb" }));
app.use("/events", eventsRouter);
app.use("/users", usersRouter);
app.use("/enrollments", enrollmentsRouter);
app.use("/enrollment-requests", enrollmentRequestsRouter);
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
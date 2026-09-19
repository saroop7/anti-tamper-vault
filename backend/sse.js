// A minimal Server-Sent Events hub: frontend pages open one long-lived GET
// connection here instead of polling on a fixed timer, and get pushed a
// short "something changed" signal the instant new data lands. The
// frontend then refetches the relevant list itself -- this only carries a
// type name, never the payload, so the response shape everyone already
// trusts (GET /events, GET /enrollments, ...) stays the single source of
// truth.
const clients = new Set();

export function sseHandler(req, res) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  res.write("\n");
  clients.add(res);
  req.on("close", () => clients.delete(res));
}

export function broadcast(type) {
  const payload = `data: ${type}\n\n`;
  for (const res of clients) {
    try {
      res.write(payload);
    } catch (e) {
      clients.delete(res);
    }
  }
}

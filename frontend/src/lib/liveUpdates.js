import { useEffect, useRef } from "react";
import { API } from "./api";

// Subscribes to the backend's Server-Sent Events stream and calls
// onMessage(type) the instant the backend broadcasts a change -- lets a
// page refresh itself the moment new data lands, instead of waiting for
// the next poll tick. EventSource reconnects on its own if the connection
// drops (network blip, backend restart), so no manual retry logic needed.
export function useLiveUpdates(onMessage) {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage; // always call the latest closure, no stale refresh()

  useEffect(() => {
    let es;
    try {
      es = new EventSource(`${API}/stream`);
      es.onmessage = (e) => handlerRef.current(e.data);
    } catch (e) {
      // EventSource isn't available or the URL is unreachable -- the
      // page's own poll interval is still the fallback, so this is silent
    }
    return () => es?.close();
  }, []);
}

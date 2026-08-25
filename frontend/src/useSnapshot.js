import { useEffect, useRef, useState } from "react";

// The whole data layer in one hook: an initial fetch for instant paint, then a
// long-lived EventSource fed by the backend's poll loop. EventSource handles
// its own reconnects (the server sends `retry: 3000`); we only recreate it
// when the browser gives up entirely (readyState CLOSED).
export function useSnapshot() {
  const [snapshot, setSnapshot] = useState(null);
  const [connected, setConnected] = useState(false);
  const gotSse = useRef(false);

  useEffect(() => {
    let source;
    let retryTimer;
    let closed = false;

    fetch("/api/snapshot")
      .then((r) => (r.ok ? r.json() : null))
      .then((snap) => {
        if (snap && !gotSse.current) setSnapshot(snap);
      })
      .catch(() => {});

    const connect = () => {
      if (closed) return;
      source = new EventSource("/api/stream");
      source.onopen = () => setConnected(true);
      source.addEventListener("snapshot", (e) => {
        gotSse.current = true;
        setConnected(true);
        try {
          setSnapshot(JSON.parse(e.data));
        } catch {
          /* malformed frame — wait for the next one */
        }
      });
      source.onerror = () => {
        setConnected(false);
        if (source.readyState === EventSource.CLOSED) {
          retryTimer = setTimeout(connect, 3000);
        }
      };
    };
    connect();

    return () => {
      closed = true;
      clearTimeout(retryTimer);
      if (source) source.close();
    };
  }, []);

  return { snapshot, connected };
}

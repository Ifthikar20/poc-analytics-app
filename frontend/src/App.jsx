import React from "react";
import { useSnapshot } from "./useSnapshot.js";
import LiveCounter from "./components/LiveCounter.jsx";
import MinuteChart from "./components/MinuteChart.jsx";
import TopList from "./components/TopList.jsx";
import SourceBadge from "./components/SourceBadge.jsx";
import ConnectionStatus from "./components/ConnectionStatus.jsx";

export default function App() {
  const { snapshot, connected } = useSnapshot();

  return (
    <div className="page">
      <header className="header">
        <h1>Realtime Traffic Tracker</h1>
        <div className="header-right">
          {snapshot && <SourceBadge source={snapshot.source} fetchedAt={snapshot.fetched_at} />}
          <ConnectionStatus connected={connected} />
          <a className="demo-link" href="/demo" target="_blank" rel="noreferrer">
            Open demo site ↗
          </a>
        </div>
      </header>
      <p className="subtitle">
        No-database live analytics: script tag → GA4 / Cloudflare / local store → polling
        proxy → server-sent events → this page.
      </p>

      {!snapshot ? (
        <div className="card placeholder">Connecting to the live stream…</div>
      ) : (
        <>
          <div className="grid main-grid">
            <div className="card">
              <LiveCounter
                value={snapshot.active_users}
                windowMinutes={snapshot.active_window_minutes}
              />
            </div>
            <div className="card">
              <MinuteChart series={snapshot.per_minute} />
            </div>
          </div>
          <div className="grid lists-grid">
            <div className="card">
              <TopList title="Top pages" items={snapshot.top_pages} unit="views" />
            </div>
            <div className="card">
              <TopList title="Top countries" items={snapshot.top_countries} unit="visitors" />
            </div>
          </div>
          {snapshot.notes.length > 0 && (
            <footer className="notes">
              {snapshot.notes.map((note) => (
                <div key={note}>· {note}</div>
              ))}
            </footer>
          )}
        </>
      )}
    </div>
  );
}

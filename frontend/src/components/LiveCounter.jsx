import React from "react";

export default function LiveCounter({ value, windowMinutes }) {
  return (
    <div className="live-counter">
      <div className="live-label">
        <span className="pulse-dot" /> LIVE
      </div>
      <div className="live-value">{value}</div>
      <div className="live-caption">active visitors in the last {windowMinutes} min</div>
    </div>
  );
}

import React from "react";

export default function TopList({ title, items, unit }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="top-list">
      <h2>{title}</h2>
      {items.length === 0 ? (
        <div className="empty">No data yet</div>
      ) : (
        items.map((item) => (
          <div className="top-row" key={item.name}>
            <div className="top-bar" style={{ width: `${(item.value / max) * 100}%` }} />
            <span className="top-name" title={item.name}>{item.name}</span>
            <span className="top-value">
              {item.value} {item.value === 1 ? unit.replace(/s$/, "") : unit}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

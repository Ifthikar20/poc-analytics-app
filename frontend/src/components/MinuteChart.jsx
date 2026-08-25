import React, { useState } from "react";

const W = 600;
const H = 150;
const PAD_TOP = 10;
const BAR = 16;
const GAP = 4;
const STEP = BAR + GAP;

// Rounded corners on the data end (top) only — the baseline stays square.
function barPath(x, y, width, height, r) {
  const radius = Math.min(r, height, width / 2);
  return [
    `M${x},${y + radius}`,
    `Q${x},${y} ${x + radius},${y}`,
    `L${x + width - radius},${y}`,
    `Q${x + width},${y} ${x + width},${y + radius}`,
    `L${x + width},${y + height}`,
    `L${x},${y + height}`,
    "Z",
  ].join(" ");
}

export default function MinuteChart({ series }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(1, ...series.map((b) => b.pageviews));

  return (
    <div className="minute-chart">
      <div className="chart-head">
        <h2>Pageviews per minute</h2>
        <span className="chart-max">peak {max}/min</span>
      </div>
      <div className="chart-plot">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="Pageviews per minute over the last 30 minutes"
        >
          {series.map((bucket, i) => {
            const h = Math.max(2, (bucket.pageviews / max) * (H - PAD_TOP));
            const cls = [
              "bar",
              bucket.minutes_ago === 0 ? "bar-now" : "",
              hover === i ? "bar-hover" : "",
            ]
              .join(" ")
              .trim();
            return (
              <path key={bucket.minutes_ago} d={barPath(i * STEP, H - h, BAR, h, 3)} className={cls} />
            );
          })}
          {/* Full-height invisible hit targets, wider than the bars themselves */}
          {series.map((bucket, i) => (
            <rect
              key={`hit-${bucket.minutes_ago}`}
              x={i * STEP - GAP / 2}
              y="0"
              width={STEP}
              height={H}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            />
          ))}
        </svg>
        {hover !== null && series[hover] && (
          <div
            className="chart-tooltip"
            style={{ left: `${Math.min(90, Math.max(10, (((hover + 0.5) * STEP) / W) * 100))}%` }}
          >
            <strong>{series[hover].pageviews}</strong>{" "}
            {series[hover].pageviews === 1 ? "view" : "views"} ·{" "}
            {series[hover].minutes_ago === 0
              ? "this minute"
              : `${series[hover].minutes_ago} min ago`}
          </div>
        )}
      </div>
      <div className="chart-axis">
        <span>30 min ago</span>
        <span>now</span>
      </div>
    </div>
  );
}

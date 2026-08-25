import React, { useEffect, useState } from "react";

const LABELS = { demo: "DEMO", ga4: "GA4", cloudflare: "CLOUDFLARE" };

export default function SourceBadge({ source, fetchedAt }) {
  const [ageSeconds, setAgeSeconds] = useState(0);

  useEffect(() => {
    const compute = () =>
      setAgeSeconds(Math.max(0, Math.round((Date.now() - Date.parse(fetchedAt)) / 1000)));
    compute();
    const timer = setInterval(compute, 1000);
    return () => clearInterval(timer);
  }, [fetchedAt]);

  return (
    <span className={`badge badge-${source}`}>
      {LABELS[source] || source} · updated {ageSeconds}s ago
    </span>
  );
}

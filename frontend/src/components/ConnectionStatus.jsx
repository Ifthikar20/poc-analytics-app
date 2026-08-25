import React from "react";

export default function ConnectionStatus({ connected }) {
  return (
    <span className={connected ? "conn conn-live" : "conn conn-down"}>
      <span className="conn-dot" /> {connected ? "live" : "reconnecting…"}
    </span>
  );
}

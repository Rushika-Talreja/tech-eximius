import React from "react";

export function NotImplementedBadge() {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        backgroundColor: "#e0e0e0",
        color: "#555",
        fontSize: "11px",
        fontWeight: "bold",
        borderRadius: "3px",
        border: "1px solid #bbb",
        letterSpacing: "0.5px",
      }}
    >
      NOT IMPLEMENTED YET
    </span>
  );
}


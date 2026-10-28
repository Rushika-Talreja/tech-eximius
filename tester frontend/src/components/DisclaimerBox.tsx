import React from "react";

interface DisclaimerBoxProps {
  disclaimer?: string | null;
}

export function DisclaimerBox({ disclaimer }: DisclaimerBoxProps) {
  if (!disclaimer) return null;

  return (
    <div
      style={{
        margin: "12px 0",
        padding: "10px 14px",
        backgroundColor: "#fffbe6",
        border: "1px solid #ffe58f",
        borderRadius: "4px",
        fontSize: "12px",
        color: "#595959",
      }}
    >
      <span style={{ fontWeight: "bold", color: "#d48806", marginRight: "6px" }}>
        [DISCLAIMER]
      </span>
      {/* Strict plain text rendering */}
      <span>{String(disclaimer)}</span>
    </div>
  );
}


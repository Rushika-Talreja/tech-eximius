import React from "react";

interface DisclaimerBoxProps {
  disclaimer?: string | null;
  isRecorded?: boolean;
}

export function DisclaimerBox({ disclaimer, isRecorded }: DisclaimerBoxProps) {
  if (!disclaimer && !isRecorded) return null;

  const showRecorded = isRecorded || (disclaimer && disclaimer.includes("RECORDED"));

  return (
    <div
      style={{
        margin: "12px 0",
        padding: "10px 14px",
        backgroundColor: showRecorded ? "#fdf6e2" : "#fffbe6",
        border: `1px solid ${showRecorded ? "#f39c12" : "#ffe58f"}`,
        borderRadius: "4px",
        fontSize: "12px",
        color: "#595959",
      }}
    >
      {showRecorded && (
        <span
          style={{
            backgroundColor: "#e67e22",
            color: "#fff",
            padding: "2px 6px",
            borderRadius: "3px",
            fontSize: "11px",
            fontWeight: "bold",
            marginRight: "8px",
          }}
        >
          RECORDED
        </span>
      )}
      <span style={{ fontWeight: "bold", color: "#d48806", marginRight: "6px" }}>
        [DISCLAIMER]
      </span>
      {/* Strict plain text rendering */}
      <span>{String(disclaimer || "Pre-generated fallback analysis result for reliable presentation.")}</span>
    </div>
  );
}


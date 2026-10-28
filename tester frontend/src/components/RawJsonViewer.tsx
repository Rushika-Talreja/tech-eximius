"use client";

import React, { useState } from "react";
import { useConsole } from "../lib/store";

interface RawJsonViewerProps {
  data: any;
  title?: string;
}

export function RawJsonViewer({ data, title = "Raw JSON Response" }: RawJsonViewerProps) {
  const { showRawJson } = useConsole();
  const [localOpen, setLocalOpen] = useState(false);

  if (data === undefined || data === null) return null;

  const isOpen = showRawJson || localOpen;

  return (
    <div
      style={{
        marginTop: "16px",
        border: "1px solid #ddd",
        borderRadius: "4px",
        backgroundColor: "#fbfbfb",
      }}
    >
      <div
        onClick={() => setLocalOpen(!localOpen)}
        style={{
          padding: "8px 12px",
          backgroundColor: "#f0f0f0",
          cursor: "pointer",
          fontSize: "12px",
          fontWeight: "bold",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          userSelect: "none",
        }}
      >
        <span>
          {isOpen ? "▼" : "▶"} {title}
        </span>
        <span style={{ fontSize: "11px", color: "#666", fontWeight: "normal" }}>
          {isOpen ? "Click to hide" : "Click to inspect"}
        </span>
      </div>

      {isOpen && (
        <pre
          style={{
            margin: 0,
            padding: "12px",
            backgroundColor: "#222",
            color: "#66ff66",
            fontSize: "12px",
            fontFamily: "monospace",
            overflowX: "auto",
            maxHeight: "350px",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
          }}
        >
          {typeof data === "string" ? data : JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}


import React from "react";
import { ApiConsoleError } from "../lib/api";
import { NotImplementedBadge } from "./NotImplementedBadge";

interface ErrorDisplayProps {
  error: ApiConsoleError | Error | null;
}

export function ErrorDisplay({ error }: ErrorDisplayProps) {
  if (!error) return null;

  if (error instanceof ApiConsoleError && error.isNotImplemented) {
    return (
      <div style={{ margin: "12px 0", padding: "10px", backgroundColor: "#f9f9f9", border: "1px solid #ddd" }}>
        <NotImplementedBadge />
        <span style={{ marginLeft: "10px", fontSize: "13px", color: "#666" }}>
          (HTTP {error.status} - {error.message})
        </span>
      </div>
    );
  }

  const isApiError = error instanceof ApiConsoleError;
  const status = isApiError ? error.status : null;
  const code = isApiError ? error.code : "CLIENT_ERROR";
  const requestId = isApiError ? error.requestId : null;
  const details = isApiError ? error.details : null;

  return (
    <div
      style={{
        margin: "12px 0",
        padding: "12px",
        backgroundColor: "#fff0f0",
        border: "1px solid #ffcccc",
        borderRadius: "4px",
        fontFamily: "monospace",
        fontSize: "13px",
      }}
    >
      <div style={{ fontWeight: "bold", color: "#cc0000", marginBottom: "6px" }}>
        FAILED: {status ? `[HTTP ${status}] ` : ""}{code}
      </div>
      <div style={{ color: "#333", whiteSpace: "pre-wrap", marginBottom: "6px" }}>
        {error.message}
      </div>
      {requestId && (
        <div style={{ color: "#777", fontSize: "11px" }}>
          Request ID: <code>{requestId}</code>
        </div>
      )}
      {details && (
        <div style={{ marginTop: "6px" }}>
          <div style={{ fontSize: "11px", color: "#888", marginBottom: "2px" }}>Details:</div>
          <pre
            style={{
              margin: 0,
              padding: "6px",
              backgroundColor: "#fff",
              border: "1px solid #eee",
              overflowX: "auto",
              fontSize: "11px",
            }}
          >
            {typeof details === "string" ? details : JSON.stringify(details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}


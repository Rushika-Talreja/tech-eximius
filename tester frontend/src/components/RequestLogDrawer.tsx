"use client";

import React, { useState } from "react";
import { useConsole, RequestLogEntry } from "../lib/store";

export function RequestLogDrawer() {
  const { requestLogs, clearLogs, isDrawerOpen, setIsDrawerOpen } = useConsole();
  const [selectedEntry, setSelectedEntry] = useState<RequestLogEntry | null>(null);

  return (
    <div
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        backgroundColor: "#fff",
        borderTop: "2px solid #333",
        boxShadow: "0 -2px 10px rgba(0,0,0,0.15)",
        fontFamily: "monospace",
        fontSize: "12px",
      }}
    >
      {/* Header bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "6px 16px",
          backgroundColor: "#2c3e50",
          color: "#fff",
          cursor: "pointer",
        }}
        onClick={() => setIsDrawerOpen(!isDrawerOpen)}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontWeight: "bold" }}>
            {isDrawerOpen ? "▼" : "▲"} REQUEST LOG ({requestLogs.length} calls)
          </span>
          {requestLogs.length > 0 && (
            <span style={{ fontSize: "11px", color: "#bdc3c7" }}>
              Latest: {requestLogs[0].method} {requestLogs[0].path} [{requestLogs[0].status}] ({requestLogs[0].durationMs}ms)
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: "8px" }} onClick={(e) => e.stopPropagation()}>
          <button
            onClick={clearLogs}
            style={{
              padding: "2px 8px",
              fontSize: "11px",
              backgroundColor: "#e74c3c",
              color: "#fff",
              border: "none",
              borderRadius: "3px",
              cursor: "pointer",
            }}
          >
            Clear
          </button>
          <button
            onClick={() => setIsDrawerOpen(!isDrawerOpen)}
            style={{
              padding: "2px 8px",
              fontSize: "11px",
              backgroundColor: "#34495e",
              color: "#fff",
              border: "1px solid #7f8c8d",
              borderRadius: "3px",
              cursor: "pointer",
            }}
          >
            {isDrawerOpen ? "Close Drawer" : "Open Drawer"}
          </button>
        </div>
      </div>

      {/* Expanded drawer body */}
      {isDrawerOpen && (
        <div
          style={{
            height: "260px",
            display: "flex",
            backgroundColor: "#f8f9fa",
            borderTop: "1px solid #ddd",
          }}
        >
          {/* Calls list */}
          <div
            style={{
              flex: "0 0 450px",
              overflowY: "auto",
              borderRight: "1px solid #ddd",
            }}
          >
            {requestLogs.length === 0 ? (
              <div style={{ padding: "16px", color: "#888", textAlign: "center" }}>
                No API calls recorded yet.
              </div>
            ) : (
              requestLogs.map((log) => {
                const isSelected = selectedEntry?.id === log.id;
                let statusColor = "#27ae60"; // green
                if (log.status >= 400 && log.status < 500) statusColor = "#e67e22"; // orange
                if (log.status >= 500) statusColor = "#c0392b"; // red
                if (log.isNotImplemented) statusColor = "#7f8c8d"; // grey

                return (
                  <div
                    key={log.id}
                    onClick={() => setSelectedEntry(log)}
                    style={{
                      padding: "6px 12px",
                      borderBottom: "1px solid #eee",
                      backgroundColor: isSelected ? "#e8f4fc" : "#fff",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: "bold", width: "50px", display: "inline-block" }}>
                        {log.method}
                      </span>
                      <span style={{ color: "#333" }}>{log.path}</span>
                    </div>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <span style={{ color: "#888", fontSize: "11px" }}>{log.durationMs}ms</span>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "1px 6px",
                          borderRadius: "3px",
                          backgroundColor: statusColor,
                          color: "#fff",
                          fontWeight: "bold",
                          fontSize: "11px",
                        }}
                      >
                        {log.isNotImplemented ? "NOT IMPL" : log.status || "ERR"}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Call details */}
          <div style={{ flex: 1, overflowY: "auto", padding: "12px", backgroundColor: "#fff" }}>
            {selectedEntry ? (
              <div>
                <div style={{ fontWeight: "bold", fontSize: "13px", marginBottom: "8px" }}>
                  {selectedEntry.method} {selectedEntry.path} &mdash; Status: {selectedEntry.status} ({selectedEntry.durationMs}ms)
                </div>
                <div style={{ color: "#666", marginBottom: "8px" }}>
                  Request ID: <code>{selectedEntry.requestId}</code> | Time: {selectedEntry.timestamp}
                </div>

                <div style={{ marginTop: "10px" }}>
                  <strong>Request Payload:</strong>
                  <pre
                    style={{
                      backgroundColor: "#f4f4f4",
                      padding: "8px",
                      maxHeight: "80px",
                      overflowY: "auto",
                      margin: "4px 0",
                    }}
                  >
                    {selectedEntry.requestBody ? JSON.stringify(selectedEntry.requestBody, null, 2) : "(empty)"}
                  </pre>
                </div>

                <div style={{ marginTop: "10px" }}>
                  <strong>Response Body:</strong>
                  <pre
                    style={{
                      backgroundColor: "#f4f4f4",
                      padding: "8px",
                      maxHeight: "120px",
                      overflowY: "auto",
                      margin: "4px 0",
                    }}
                  >
                    {selectedEntry.responseBody !== undefined
                      ? typeof selectedEntry.responseBody === "string"
                        ? selectedEntry.responseBody
                        : JSON.stringify(selectedEntry.responseBody, null, 2)
                      : "(empty)"}
                  </pre>
                </div>
              </div>
            ) : (
              <div style={{ padding: "20px", color: "#888", textAlign: "center" }}>
                Select a request from the left list to inspect headers, payload, and response.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


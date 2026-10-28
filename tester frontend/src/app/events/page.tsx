"use client";

import React, { useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { AuditEventItem } from "../../types/backend";

export default function EventsPage() {
  const searchParams = useSearchParams();
  const initialAuditId = searchParams.get("audit_id") || "";

  const { authMode, apiKey, addLogEntry } = useConsole();
  const [auditId, setAuditId] = useState(initialAuditId);
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [usePollingFallback, setUsePollingFallback] = useState(false);
  const [lastEventId, setLastEventId] = useState<number | null>(null);
  const [error, setError] = useState<any>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      stopStream();
    };
  }, []);

  const stopStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setIsStreaming(false);
  };

  const startStream = () => {
    if (!auditId.trim()) {
      alert("Please enter a valid Audit UUID");
      return;
    }
    stopStream();
    setError(null);
    setIsStreaming(true);

    if (usePollingFallback) {
      startPolling();
    } else {
      startSSE();
    }
  };

  const startSSE = () => {
    // SSE endpoint
    const url = `/api/backend/v1/audits/${auditId.trim()}/events`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        const item: AuditEventItem = {
          id: Number(event.lastEventId) || Date.now(),
          audit_id: auditId,
          org_id: parsed.org_id || "",
          ts: parsed.ts || new Date().toISOString(),
          stage: parsed.stage || null,
          level: parsed.level || "info",
          message: parsed.message || event.data,
          data: parsed.data,
        };

        if (event.lastEventId) {
          setLastEventId(Number(event.lastEventId));
        }

        setEvents((prev) => [item, ...prev]);
      } catch {
        // Plain text message
        setEvents((prev) => [
          {
            id: Date.now(),
            audit_id: auditId,
            org_id: "",
            ts: new Date().toISOString(),
            stage: null,
            level: "info",
            message: event.data,
          },
          ...prev,
        ]);
      }
    };

    es.onerror = () => {
      setError(new Error("SSE connection closed or lost. Click Poll Fallback to resume."));
      stopStream();
    };
  };

  const startPolling = () => {
    const poll = async () => {
      try {
        const res = await executeApiRequest(`/audits/${auditId.trim()}/events`, {
          authMode,
          apiKey,
          onLog: addLogEntry,
        });

        if (Array.isArray(res.data?.items)) {
          setEvents(res.data.items);
          if (res.data.items.length > 0) {
            setLastEventId(res.data.items[res.data.items.length - 1].id);
          }
        }
      } catch (err) {
        setError(err);
      }
    };

    poll();
    pollTimerRef.current = setInterval(poll, 2500);
  };

  return (
    <div>
      <h2>Live Progress (SSE Stream)</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Real-time event stream from <code>GET /audits/&#123;id&#125;/events</code> with <code>Last-Event-ID</code> resume and HTTP polling fallback.
      </p>

      {/* Controller box */}
      <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa", marginBottom: "20px" }}>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Audit ID (UUID):</label>
            <input
              type="text"
              value={auditId}
              onChange={(e) => setAuditId(e.target.value)}
              placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
              style={{ width: "320px", padding: "6px", fontFamily: "monospace" }}
            />
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "13px", cursor: "pointer", marginTop: "14px" }}>
            <input
              type="checkbox"
              checked={usePollingFallback}
              onChange={(e) => setUsePollingFallback(e.target.checked)}
            />
            <span>Use HTTP Polling Fallback (every 2.5s)</span>
          </label>

          <div style={{ marginTop: "14px" }}>
            {!isStreaming ? (
              <button
                onClick={startStream}
                style={{
                  padding: "6px 14px",
                  backgroundColor: "#27ae60",
                  color: "#fff",
                  border: "none",
                  borderRadius: "4px",
                  fontWeight: "bold",
                  cursor: "pointer",
                }}
              >
                Connect Stream
              </button>
            ) : (
              <button
                onClick={stopStream}
                style={{
                  padding: "6px 14px",
                  backgroundColor: "#c0392b",
                  color: "#fff",
                  border: "none",
                  borderRadius: "4px",
                  fontWeight: "bold",
                  cursor: "pointer",
                }}
              >
                Disconnect
              </button>
            )}
          </div>

          <button
            onClick={() => setEvents([])}
            style={{ marginTop: "14px", padding: "6px 12px", cursor: "pointer" }}
          >
            Clear Events
          </button>
        </div>

        <div style={{ marginTop: "10px", fontSize: "12px", color: "#666" }}>
          Stream State:{" "}
          <strong style={{ color: isStreaming ? "#27ae60" : "#c0392b" }}>
            {isStreaming ? (usePollingFallback ? "POLLING ACTIVE" : "SSE CONNECTED") : "DISCONNECTED"}
          </strong>{" "}
          | Last-Event-ID: <code>{lastEventId !== null ? lastEventId : "None"}</code>
        </div>
      </div>

      <ErrorDisplay error={error} />

      {/* Events table */}
      <h3 style={{ margin: "0 0 8px 0" }}>Event Log ({events.length} events)</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ backgroundColor: "#f0f0f0", textAlign: "left" }}>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "80px" }}>ID</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "180px" }}>Timestamp</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "120px" }}>Stage</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "70px" }}>Level</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Message</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "200px" }}>Data</th>
          </tr>
        </thead>
        <tbody>
          {events.length === 0 ? (
            <tr>
              <td colSpan={6} style={{ padding: "16px", textAlign: "center", color: "#888" }}>
                No events streamed yet. Connect to an active audit above.
              </td>
            </tr>
          ) : (
            events.map((ev, idx) => (
              <tr key={idx} style={{ backgroundColor: idx % 2 === 0 ? "#fff" : "#fafafa" }}>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace" }}>
                  {ev.id}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", color: "#666" }}>
                  {ev.ts}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontWeight: "bold" }}>
                  {ev.stage || "-"}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  <span
                    style={{
                      color: ev.level === "error" ? "#c0392b" : ev.level === "warn" ? "#d35400" : "#27ae60",
                      fontWeight: "bold",
                    }}
                  >
                    {ev.level}
                  </span>
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  {ev.message}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace", fontSize: "11px" }}>
                  {ev.data ? JSON.stringify(ev.data) : "-"}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <RawJsonViewer data={events} title="Raw Events JSON" />
    </div>
  );
}


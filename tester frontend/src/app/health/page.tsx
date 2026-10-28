"use client";

import React, { useState } from "react";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";

export default function HealthPage() {
  const { authMode, apiKey, addLogEntry } = useConsole();
  const [healthData, setHealthData] = useState<any>(null);
  const [healthError, setHealthError] = useState<any>(null);
  const [meData, setMeData] = useState<any>(null);
  const [meError, setMeError] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchHealth = async () => {
    setHealthError(null);
    try {
      const res = await executeApiRequest("/health", {
        authMode: "none",
        onLog: addLogEntry,
      });
      setHealthData(res.data);
    } catch (err) {
      setHealthError(err);
      setHealthData(null);
    }
  };

  const fetchMe = async () => {
    setMeError(null);
    try {
      const res = await executeApiRequest("/me", {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setMeData(res.data);
    } catch (err) {
      setMeError(err);
      setMeData(null);
    }
  };

  const runBoth = async () => {
    setLoading(true);
    await Promise.all([fetchHealth(), fetchMe()]);
    setLoading(false);
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Health & Identity Inspection</h2>
        <button
          onClick={runBoth}
          disabled={loading}
          style={{
            padding: "8px 16px",
            backgroundColor: "#0066cc",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            fontWeight: "bold",
          }}
        >
          {loading ? "Checking..." : "Inspect Both Endpoints"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginTop: "20px" }}>
        {/* GET /health */}
        <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>GET /health</h3>
            <button onClick={fetchHealth} style={{ padding: "4px 8px" }}>Refresh</button>
          </div>
          <p style={{ color: "#666", fontSize: "12px", margin: "4px 0 12px 0" }}>
            Public probe. Requires no authentication.
          </p>

          <ErrorDisplay error={healthError} />

          {healthData && (
            <div style={{ fontFamily: "monospace", fontSize: "13px" }}>
              <div>Status: <strong>{healthData.status}</strong></div>
              <div>Version: <strong>{healthData.version}</strong></div>
            </div>
          )}

          <RawJsonViewer data={healthData} title="Raw Health Response" />
        </div>

        {/* GET /me */}
        <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>GET /me</h3>
            <button onClick={fetchMe} style={{ padding: "4px 8px" }}>Refresh</button>
          </div>
          <p style={{ color: "#666", fontSize: "12px", margin: "4px 0 12px 0" }}>
            Authenticated identity probe using current header mode: <strong>{authMode}</strong>
          </p>

          <ErrorDisplay error={meError} />

          {meData && (
            <div style={{ fontFamily: "monospace", fontSize: "13px" }}>
              <div>User ID: <strong>{meData.user?.id}</strong></div>
              <div>Email: <strong>{meData.user?.email}</strong></div>
              <div>Role: <strong>{meData.user?.role}</strong></div>
              <div style={{ marginTop: "8px" }}>Org ID: <strong>{meData.org?.id}</strong></div>
              <div>Org Name: <strong>{meData.org?.name}</strong></div>
              <div style={{ marginTop: "8px" }}>Upload Limit: <strong>{meData.limits?.max_upload_mb} MB</strong></div>
              <div>Hourly Audit Limit: <strong>{meData.limits?.audits_per_hour}</strong></div>
            </div>
          )}

          <RawJsonViewer data={meData} title="Raw /me Response" />
        </div>
      </div>
    </div>
  );
}


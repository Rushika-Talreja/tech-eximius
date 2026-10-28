"use client";

import React, { useEffect, useState } from "react";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { CorpusVersionsResponse } from "../../types/backend";

export default function CorpusPage() {
  const { authMode, apiKey, addLogEntry } = useConsole();
  const [corpusData, setCorpusData] = useState<CorpusVersionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const fetchCorpus = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await executeApiRequest<CorpusVersionsResponse>("/corpus/versions", {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setCorpusData(res.data);
    } catch (err) {
      setError(err);
      setCorpusData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCorpus();
  }, [authMode]);

  return (
    <div>
      <h2>Security Corpus Versions</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>GET /corpus/versions</code> &mdash; public security precedent database version tracking.
      </p>

      <div style={{ marginBottom: "16px" }}>
        <button
          onClick={fetchCorpus}
          disabled={loading}
          style={{
            padding: "6px 14px",
            backgroundColor: "#2980b9",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            fontWeight: "bold",
            cursor: "pointer",
          }}
        >
          {loading ? "Fetching..." : "Fetch Corpus Versions"}
        </button>
      </div>

      <ErrorDisplay error={error} />

      {corpusData && (
        <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa" }}>
          <div style={{ fontSize: "13px", fontFamily: "monospace" }}>
            <div>Current Version: <strong>{corpusData.current_version || "Not seeded"}</strong></div>
            <div>Document Count: <strong>{corpusData.document_count ?? 0}</strong></div>
            <div style={{ marginTop: "10px" }}>Available Versions:</div>
            <ul style={{ margin: "4px 0", paddingLeft: "20px" }}>
              {corpusData.versions?.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <RawJsonViewer data={corpusData} title="Raw Corpus Versions JSON" />
    </div>
  );
}


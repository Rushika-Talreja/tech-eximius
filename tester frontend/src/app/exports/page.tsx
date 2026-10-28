"use client";

import React, { useState } from "react";
import { useSearchParams } from "next/navigation";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";

export default function ExportsPage() {
  const searchParams = useSearchParams();
  const initialAuditId = searchParams.get("audit_id") || "";

  const { authMode, apiKey, addLogEntry } = useConsole();
  const [auditId, setAuditId] = useState(initialAuditId);
  const [exportContent, setExportContent] = useState<string>("");
  const [exportFormat, setExportFormat] = useState<string>("");
  const [fileSizeBytes, setFileSizeBytes] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const handleExport = async (format: "json" | "md" | "sarif" | "pdf") => {
    if (!auditId.trim()) {
      alert("Please enter an Audit ID");
      return;
    }
    setLoading(true);
    setError(null);
    setExportContent("");
    setExportFormat(format);

    try {
      const res = await executeApiRequest(`/audits/${auditId.trim()}/export?format=${format}`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });

      let textOutput = "";
      if (typeof res.data === "string") {
        textOutput = res.data;
      } else {
        textOutput = JSON.stringify(res.data, null, 2);
      }

      setExportContent(textOutput);
      setFileSizeBytes(new TextEncoder().encode(textOutput).length);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadFile = () => {
    if (!exportContent) return;
    const blob = new Blob([exportContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_${auditId.substring(0, 8)}_export.${exportFormat === "sarif" ? "sarif.json" : exportFormat}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const first40Lines = exportContent.split("\n").slice(0, 40).join("\n");

  return (
    <div>
      <h2>Report Exports (JSON, Markdown, SARIF, PDF)</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>GET /audits/&#123;id&#125;/export?format=...</code> and <code>GET /audits/&#123;id&#125;/report</code>.
      </p>

      {/* Audit Picker & Format Triggers */}
      <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa", marginBottom: "20px" }}>
        <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "12px" }}>
          <input
            type="text"
            value={auditId}
            onChange={(e) => setAuditId(e.target.value)}
            placeholder="Enter Audit UUID"
            style={{ width: "320px", padding: "6px", fontFamily: "monospace" }}
          />
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={() => handleExport("json")}
            disabled={loading}
            style={{ padding: "8px 16px", backgroundColor: "#27ae60", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "bold", cursor: "pointer" }}
          >
            Export JSON
          </button>
          <button
            onClick={() => handleExport("md")}
            disabled={loading}
            style={{ padding: "8px 16px", backgroundColor: "#2980b9", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "bold", cursor: "pointer" }}
          >
            Export Markdown
          </button>
          <button
            onClick={() => handleExport("sarif")}
            disabled={loading}
            style={{ padding: "8px 16px", backgroundColor: "#8e44ad", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "bold", cursor: "pointer" }}
          >
            Export SARIF
          </button>
          <button
            onClick={() => handleExport("pdf")}
            disabled={loading}
            style={{ padding: "8px 16px", backgroundColor: "#d35400", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "bold", cursor: "pointer" }}
          >
            Export PDF (or stub)
          </button>
        </div>
      </div>

      <ErrorDisplay error={error} />

      {/* Preview Section */}
      {exportContent && (
        <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <h4 style={{ margin: 0 }}>
              Export Output ({exportFormat.toUpperCase()}) &mdash; Size: {fileSizeBytes} bytes
            </h4>
            <button
              onClick={handleDownloadFile}
              style={{
                padding: "6px 14px",
                backgroundColor: "#0066cc",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                fontWeight: "bold",
              }}
            >
              Download Full File
            </button>
          </div>

          <p style={{ fontSize: "12px", color: "#666", margin: "0 0 6px 0" }}>
            First 40 lines preview:
          </p>
          <pre
            style={{
              backgroundColor: "#222",
              color: "#e6edf3",
              padding: "12px",
              fontSize: "12px",
              fontFamily: "monospace",
              lineHeight: "1.4",
              overflowX: "auto",
              maxHeight: "450px",
              whiteSpace: "pre-wrap",
            }}
          >
            {first40Lines}
          </pre>
        </div>
      )}

      <RawJsonViewer data={exportContent ? { format: exportFormat, size_bytes: fileSizeBytes } : null} title="Export Metadata" />
    </div>
  );
}


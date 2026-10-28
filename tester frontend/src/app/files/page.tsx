"use client";

import React, { useState } from "react";
import { useSearchParams } from "next/navigation";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { AuditFileItem } from "../../types/backend";

export default function FilesPage() {
  const searchParams = useSearchParams();
  const initialAuditId = searchParams.get("audit_id") || "";

  const { authMode, apiKey, addLogEntry } = useConsole();
  const [auditId, setAuditId] = useState(initialAuditId);
  const [files, setFiles] = useState<AuditFileItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<AuditFileItem | null>(null);
  const [fileContent, setFileContent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const fetchFiles = async () => {
    if (!auditId.trim()) {
      alert("Please enter an Audit ID");
      return;
    }
    setLoading(true);
    setError(null);
    setSelectedFile(null);
    setFileContent("");

    try {
      const res = await executeApiRequest(`/audits/${auditId.trim()}/files`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setFiles(res.data?.items || []);
    } catch (err) {
      setError(err);
      setFiles([]);
    } finally {
      setLoading(false);
    }
  };

  const loadFileContent = async (file: AuditFileItem) => {
    setSelectedFile(file);
    setLoading(true);
    setError(null);
    try {
      const res = await executeApiRequest(`/audits/${auditId.trim()}/files/${file.id}`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setFileContent(res.data?.content || "");
    } catch (err) {
      setError(err);
      setFileContent("");
    } finally {
      setLoading(false);
    }
  };

  const lines = fileContent.split("\n");

  return (
    <div>
      <h2>Files & Read-Only Code Viewer</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>GET /audits/&#123;id&#125;/files</code> and <code>GET /audits/&#123;id&#125;/files/&#123;file_id&#125;</code>.
      </p>

      {/* Audit Picker */}
      <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "16px" }}>
        <input
          type="text"
          value={auditId}
          onChange={(e) => setAuditId(e.target.value)}
          placeholder="Enter Audit UUID"
          style={{ width: "320px", padding: "6px", fontFamily: "monospace" }}
        />
        <button
          onClick={fetchFiles}
          disabled={loading}
          style={{
            padding: "6px 14px",
            backgroundColor: "#2980b9",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          {loading ? "Loading..." : "Fetch Files"}
        </button>
      </div>

      <ErrorDisplay error={error} />

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "20px" }}>
        {/* Left: Files Tree / List */}
        <div style={{ border: "1px solid #ddd", borderRadius: "4px", backgroundColor: "#fafafa", padding: "12px" }}>
          <h4 style={{ margin: "0 0 10px 0" }}>Contract Files ({files.length})</h4>
          {files.length === 0 ? (
            <div style={{ fontSize: "12px", color: "#888" }}>No files listed. Fetch with Audit UUID.</div>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "13px" }}>
              {files.map((f) => {
                const isSelected = selectedFile?.id === f.id;
                return (
                  <li
                    key={f.id}
                    onClick={() => loadFileContent(f)}
                    style={{
                      padding: "6px 8px",
                      cursor: "pointer",
                      borderBottom: "1px solid #eee",
                      backgroundColor: isSelected ? "#eaf2f8" : "transparent",
                      fontWeight: isSelected ? "bold" : "normal",
                      wordBreak: "break-all",
                    }}
                  >
                    <div>{f.path}</div>
                    <div style={{ fontSize: "11px", color: "#888" }}>
                      {f.line_count} lines {f.is_dependency ? "(dependency)" : ""}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Right: Code Viewer */}
        <div style={{ border: "1px solid #ddd", borderRadius: "4px", backgroundColor: "#fff", padding: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <h4 style={{ margin: 0 }}>
              {selectedFile ? selectedFile.path : "Select a file to inspect source"}
            </h4>
            {selectedFile && (
              <span style={{ fontSize: "11px", color: "#666", fontFamily: "monospace" }}>
                SHA256: {selectedFile.sha256}
              </span>
            )}
          </div>

          {selectedFile ? (
            <div
              style={{
                border: "1px solid #eee",
                backgroundColor: "#f9f9f9",
                fontFamily: "monospace",
                fontSize: "12px",
                lineHeight: "1.5",
                overflowX: "auto",
                maxHeight: "600px",
              }}
            >
              {lines.map((line, idx) => (
                <div key={idx} style={{ display: "flex", minWidth: "fit-content" }}>
                  <span
                    style={{
                      width: "45px",
                      textAlign: "right",
                      paddingRight: "10px",
                      userSelect: "none",
                      color: "#999",
                      backgroundColor: "#f0f0f0",
                      borderRight: "1px solid #ddd",
                      flexShrink: 0,
                    }}
                  >
                    {idx + 1}
                  </span>
                  <span style={{ paddingLeft: "10px", whiteSpace: "pre" }}>{line}</span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: "40px", textAlign: "center", color: "#999", fontSize: "13px" }}>
              Select a contract from the file list to view full line-numbered source code.
            </div>
          )}
        </div>
      </div>

      <RawJsonViewer data={files} title="Raw Files List JSON" />
    </div>
  );
}


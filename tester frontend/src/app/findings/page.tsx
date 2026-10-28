"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { DisclaimerBox } from "../../components/DisclaimerBox";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { FindingItem, FindingEvidenceItem } from "../../types/backend";

export default function FindingsPage() {
  const searchParams = useSearchParams();
  const initialAuditId = searchParams.get("audit_id") || "";

  const { authMode, apiKey, addLogEntry } = useConsole();
  const [auditId, setAuditId] = useState(initialAuditId);
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<FindingItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const fetchFindings = async () => {
    if (!auditId.trim()) {
      alert("Please enter an Audit ID");
      return;
    }
    setLoading(true);
    setError(null);
    setSelectedFinding(null);

    const params = new URLSearchParams();
    if (severityFilter) params.append("severity", severityFilter);
    if (sourceFilter) params.append("source", sourceFilter);
    if (statusFilter) params.append("status", statusFilter);

    try {
      const qs = params.toString() ? `?${params.toString()}` : "";
      const res = await executeApiRequest(`/audits/${auditId.trim()}/findings${qs}`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setFindings(res.data?.items || []);
    } catch (err) {
      setError(err);
      setFindings([]);
    } finally {
      setLoading(false);
    }
  };

  const inspectFinding = async (findingId: string) => {
    setError(null);
    try {
      const res = await executeApiRequest<FindingItem>(`/audits/${auditId.trim()}/findings/${findingId}`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setSelectedFinding(res.data);
    } catch (err) {
      setError(err);
    }
  };

  const handleToggleStatus = async (finding: FindingItem) => {
    const newStatus = finding.status === "dismissed" ? "open" : "dismissed";
    setError(null);
    try {
      await executeApiRequest(`/audits/${auditId.trim()}/findings/${finding.id}`, {
        method: "PATCH",
        body: { status: newStatus },
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      inspectFinding(finding.id);
      fetchFindings();
    } catch (err) {
      setError(err);
    }
  };

  const scoredFindings = findings.filter((f) => f.scored !== false);
  const unverifiedObservations = findings.filter((f) => f.scored === false);

  return (
    <div>
      <h2>Findings & Evidence Inspector</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>GET /audits/&#123;id&#125;/findings</code>, <code>GET /audits/&#123;id&#125;/findings/&#123;fid&#125;</code>, and <code>PATCH /audits/&#123;id&#125;/findings/&#123;fid&#125;</code>.
      </p>

      {/* Audit Picker & Filters */}
      <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa", marginBottom: "20px" }}>
        <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Audit ID:</label>
            <input
              type="text"
              value={auditId}
              onChange={(e) => setAuditId(e.target.value)}
              placeholder="Enter Audit UUID"
              style={{ width: "260px", padding: "6px", fontFamily: "monospace" }}
            />
          </div>

          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Severity:</label>
            <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} style={{ padding: "6px" }}>
              <option value="">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Source:</label>
            <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} style={{ padding: "6px" }}>
              <option value="">All Sources</option>
              <option value="slither">Slither</option>
              <option value="privilege_map">Privilege Map</option>
              <option value="rag">Security RAG</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Status:</label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: "6px" }}>
              <option value="">All Statuses</option>
              <option value="open">Open</option>
              <option value="dismissed">Dismissed</option>
            </select>
          </div>

          <div style={{ marginTop: "16px" }}>
            <button
              onClick={fetchFindings}
              disabled={loading}
              style={{
                padding: "6px 14px",
                backgroundColor: "#e67e22",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                fontWeight: "bold",
                cursor: "pointer",
              }}
            >
              {loading ? "Loading..." : "Filter & Fetch"}
            </button>
          </div>
        </div>
      </div>

      <ErrorDisplay error={error} />
      <DisclaimerBox disclaimer={selectedFinding?.disclaimer} />

      {/* Scored Findings Table */}
      <h3 style={{ margin: "0 0 8px 0" }}>Scored Findings ({scoredFindings.length})</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ backgroundColor: "#f0f0f0", textAlign: "left" }}>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Severity</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Title</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Source</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Confidence</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Status</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "120px" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {scoredFindings.length === 0 ? (
            <tr>
              <td colSpan={6} style={{ padding: "16px", textAlign: "center", color: "#888" }}>
                No findings retrieved.
              </td>
            </tr>
          ) : (
            scoredFindings.map((f) => (
              <tr key={f.id} style={{ backgroundColor: f.status === "dismissed" ? "#fbfbfb" : "#fff" }}>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  <span
                    style={{
                      padding: "2px 6px",
                      borderRadius: "3px",
                      color: "#fff",
                      fontWeight: "bold",
                      fontSize: "11px",
                      backgroundColor:
                        f.severity === "critical"
                          ? "#c0392b"
                          : f.severity === "high"
                          ? "#d35400"
                          : f.severity === "medium"
                          ? "#f39c12"
                          : f.severity === "low"
                          ? "#2980b9"
                          : "#7f8c8d",
                    }}
                  >
                    {f.severity.toUpperCase()}
                  </span>
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontWeight: "bold" }}>
                  {f.title}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace" }}>
                  {f.source}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  {Math.round(f.confidence * 100)}%
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  {f.status}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  <button
                    onClick={() => inspectFinding(f.id)}
                    style={{ padding: "2px 6px", cursor: "pointer" }}
                  >
                    Inspect
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Detail Inspection Box */}
      {selectedFinding && (
        <div style={{ marginTop: "24px", padding: "16px", border: "1px solid #34495e", borderRadius: "4px", backgroundColor: "#fdfefe" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>
              [{selectedFinding.severity.toUpperCase()}] {selectedFinding.title}
            </h3>
            <button
              onClick={() => handleToggleStatus(selectedFinding)}
              style={{
                padding: "4px 10px",
                backgroundColor: selectedFinding.status === "dismissed" ? "#27ae60" : "#7f8c8d",
                color: "#fff",
                border: "none",
                borderRadius: "3px",
                cursor: "pointer",
              }}
            >
              {selectedFinding.status === "dismissed" ? "Reopen Finding" : "Dismiss Finding"}
            </button>
          </div>

          <div style={{ margin: "10px 0", fontSize: "13px", color: "#333" }}>
            <strong>Description:</strong> {selectedFinding.description}
          </div>

          {selectedFinding.scenario && (
            <div style={{ margin: "10px 0", fontSize: "13px", color: "#555" }}>
              <strong>Attack Scenario:</strong> {selectedFinding.scenario}
            </div>
          )}

          {selectedFinding.start_line && (
            <div style={{ margin: "6px 0", fontSize: "12px", fontFamily: "monospace" }}>
              Span: Lines {selectedFinding.start_line} - {selectedFinding.end_line || selectedFinding.start_line}{" "}
              <Link href={`/files?audit_id=${auditId}`} style={{ color: "#0066cc", marginLeft: "6px" }}>
                (View in File)
              </Link>
            </div>
          )}

          {/* Evidence Cards */}
          <h4 style={{ margin: "16px 0 8px 0" }}>
            Evidence Records ({selectedFinding.evidence?.length || 0})
          </h4>
          {(!selectedFinding.evidence || selectedFinding.evidence.length === 0) ? (
            <div style={{ fontSize: "12px", color: "#888", fontStyle: "italic" }}>
              No evidence records attached to this finding.
            </div>
          ) : (
            <div style={{ display: "grid", gap: "10px" }}>
              {selectedFinding.evidence.map((ev: FindingEvidenceItem, i: number) => (
                <div key={i} style={{ border: "1px solid #ddd", padding: "10px", borderRadius: "4px", backgroundColor: "#f9f9f9", fontSize: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontWeight: "bold" }}>
                    <span>[{ev.kind}] {ev.title}</span>
                    {ev.retrieval_score && (
                      <span style={{ color: "#27ae60" }}>Score: {Math.round(ev.retrieval_score * 100)}%</span>
                    )}
                  </div>
                  {ev.locator && <div style={{ color: "#666", marginTop: "2px" }}>Locator: <code>{ev.locator}</code></div>}
                  {ev.quote && (
                    <blockquote style={{ margin: "6px 0", padding: "6px 10px", backgroundColor: "#fff", borderLeft: "3px solid #e67e22", fontFamily: "monospace" }}>
                      {ev.quote}
                    </blockquote>
                  )}
                  {ev.source_url && (
                    <div style={{ marginTop: "4px" }}>
                      Source: <a href={ev.source_url} target="_blank" rel="noreferrer" style={{ color: "#0066cc" }}>{ev.source_url}</a>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: "16px" }}>
            <Link
              href={`/patches?audit_id=${auditId}&finding_id=${selectedFinding.id}`}
              style={{
                display: "inline-block",
                padding: "6px 12px",
                backgroundColor: "#2980b9",
                color: "#fff",
                textDecoration: "none",
                borderRadius: "3px",
                fontSize: "12px",
                fontWeight: "bold",
              }}
            >
              Generate or View Patches
            </Link>
          </div>

          <RawJsonViewer data={selectedFinding} title="Raw Finding JSON" />
        </div>
      )}

      {/* Unverified Observations Section */}
      {unverifiedObservations.length > 0 && (
        <div style={{ marginTop: "30px", borderTop: "2px dashed #ddd", paddingTop: "16px" }}>
          <h3 style={{ color: "#7f8c8d" }}>Unverified Hypotheses & Observations ({unverifiedObservations.length})</h3>
          <p style={{ fontSize: "12px", color: "#888", margin: "0 0 10px 0" }}>
            Unscored observations from LLM retrieval not formally validated against static facts.
          </p>
          <ul style={{ paddingLeft: "20px", fontSize: "13px" }}>
            {unverifiedObservations.map((obs) => (
              <li key={obs.id} style={{ marginBottom: "6px" }}>
                <strong>{obs.title}</strong>: {obs.description}
              </li>
            ))}
          </ul>
        </div>
      )}

      <RawJsonViewer data={findings} title="Raw Findings List JSON" />
    </div>
  );
}


"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { DisclaimerBox } from "../../components/DisclaimerBox";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { PrivilegeMapResponse, PrivilegeResult, PrivilegedAction } from "../../types/backend";

export default function PrivilegeMapPage() {
  const searchParams = useSearchParams();
  const initialAuditId = searchParams.get("audit_id") || "";

  const { authMode, apiKey, addLogEntry } = useConsole();
  const [auditId, setAuditId] = useState(initialAuditId);
  const [privData, setPrivData] = useState<PrivilegeMapResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  // Declaration form state
  const [selectedRole, setSelectedRole] = useState("OWNER");
  const [holderType, setHolderType] = useState("multisig");
  const [threshold, setThreshold] = useState(3);
  const [signers, setSigners] = useState(5);
  const [delaySeconds, setDelaySeconds] = useState(86400);
  const [declHistory, setDeclHistory] = useState<any[]>([]);

  // Expanded actions state
  const [expandedRole, setExpandedRole] = useState<string | null>(null);

  const fetchPrivilegeMap = async () => {
    if (!auditId.trim()) {
      alert("Please enter an Audit ID");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await executeApiRequest<PrivilegeMapResponse>(`/audits/${auditId.trim()}/privilege-map`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setPrivData(res.data);
      if (res.data?.results?.length > 0 && !selectedRole) {
        setSelectedRole(res.data.results[0].role_key);
      }
    } catch (err) {
      setError(err);
      setPrivData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateDeclaration = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!auditId.trim()) return;
    setError(null);

    const oldScore = privData?.results?.find((r) => r.role_key === selectedRole)?.blast_score;

    const params: any = {};
    if (holderType === "multisig") {
      params.threshold = Number(threshold);
      params.signers = Number(signers);
    } else if (holderType === "timelock_multisig") {
      params.threshold = Number(threshold);
      params.signers = Number(signers);
      params.delay_seconds = Number(delaySeconds);
    }

    try {
      const res = await executeApiRequest(`/audits/${auditId.trim()}/role-declarations`, {
        method: "PUT",
        body: {
          declarations: [
            {
              role_key: selectedRole,
              holder_type: holderType,
              params,
            },
          ],
        },
        authMode,
        apiKey,
        onLog: addLogEntry,
      });

      // Refresh privilege map to get newly computed scores
      await fetchPrivilegeMap();

      setDeclHistory((prev) => [
        {
          timestamp: new Date().toLocaleTimeString(),
          role: selectedRole,
          holderType,
          oldScore: oldScore ?? "N/A",
          newResult: res.data,
        },
        ...prev,
      ]);
    } catch (err) {
      setError(err);
    }
  };

  return (
    <div>
      <h2>Flagship Privilege Map Inspection</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>GET /audits/&#123;id&#125;/privilege-map</code> and <code>PUT /audits/&#123;id&#125;/role-declarations</code>.
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
          onClick={fetchPrivilegeMap}
          disabled={loading}
          style={{
            padding: "6px 14px",
            backgroundColor: "#8e44ad",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            fontWeight: "bold",
            cursor: "pointer",
          }}
        >
          {loading ? "Loading Map..." : "Fetch Privilege Map"}
        </button>
      </div>

      <ErrorDisplay error={error} />
      <DisclaimerBox disclaimer={privData?.disclaimer} />

      {privData && (
        <div>
          {/* Roles Table */}
          <h3 style={{ margin: "16px 0 8px 0" }}>Roles & Privilege Blast Scores</h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ backgroundColor: "#f0f0f0", textAlign: "left" }}>
                <th style={{ padding: "8px", border: "1px solid #ddd" }}>Role Key</th>
                <th style={{ padding: "8px", border: "1px solid #ddd" }}>Blast Score</th>
                <th style={{ padding: "8px", border: "1px solid #ddd" }}>Tier</th>
                <th style={{ padding: "8px", border: "1px solid #ddd" }}>Worst Case Scenario</th>
                <th style={{ padding: "8px", border: "1px solid #ddd" }}>Holder Status</th>
                <th style={{ padding: "8px", border: "1px solid #ddd" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {privData.results?.map((r: PrivilegeResult) => {
                const isExpanded = expandedRole === r.role_key;
                return (
                  <React.Fragment key={r.role_key}>
                    <tr style={{ backgroundColor: isExpanded ? "#fbf5fc" : "#fff" }}>
                      <td style={{ padding: "8px", border: "1px solid #ddd", fontWeight: "bold", fontFamily: "monospace" }}>
                        {r.role_key}
                      </td>
                      <td style={{ padding: "8px", border: "1px solid #ddd", fontFamily: "monospace", fontWeight: "bold" }}>
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: "3px",
                            backgroundColor: r.blast_score >= 80 ? "#fadbd8" : r.blast_score >= 50 ? "#fdebd0" : "#d5f5e3",
                            color: r.blast_score >= 80 ? "#c0392b" : r.blast_score >= 50 ? "#b9770e" : "#27ae60",
                          }}
                        >
                          {r.blast_score} / 100
                        </span>
                      </td>
                      <td style={{ padding: "8px", border: "1px solid #ddd", fontWeight: "bold" }}>
                        {r.tier}
                      </td>
                      <td style={{ padding: "8px", border: "1px solid #ddd", color: "#444" }}>
                        {r.worst_case}
                      </td>
                      <td style={{ padding: "8px", border: "1px solid #ddd" }}>
                        {r.holder_assumed ? (
                          <span style={{ padding: "2px 6px", backgroundColor: "#fff3cd", color: "#856404", borderRadius: "3px", border: "1px solid #ffeeba", fontSize: "11px", fontWeight: "bold" }}>
                            Assumed: single key
                          </span>
                        ) : (
                          <span style={{ padding: "2px 6px", backgroundColor: "#d4edda", color: "#155724", borderRadius: "3px", border: "1px solid #c3e6cb", fontSize: "11px", fontWeight: "bold" }}>
                            Declared
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "8px", border: "1px solid #ddd" }}>
                        <button
                          onClick={() => setExpandedRole(isExpanded ? null : r.role_key)}
                          style={{ padding: "3px 8px", cursor: "pointer" }}
                        >
                          {isExpanded ? "Hide Powers" : "Expand Powers"}
                        </button>
                      </td>
                    </tr>

                    {/* Drilldown Powers row */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={6} style={{ padding: "12px 16px", backgroundColor: "#faf4fc", border: "1px solid #ddd" }}>
                          <h4 style={{ margin: "0 0 6px 0", fontSize: "12px", color: "#8e44ad" }}>
                            Privileged Functions Guarded by {r.role_key}:
                          </h4>
                          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", backgroundColor: "#fff" }}>
                            <thead>
                              <tr style={{ backgroundColor: "#f3e8f7", textAlign: "left" }}>
                                <th style={{ padding: "6px", border: "1px solid #e1bee7" }}>Function Signature</th>
                                <th style={{ padding: "6px", border: "1px solid #e1bee7" }}>Power Category</th>
                                <th style={{ padding: "6px", border: "1px solid #e1bee7" }}>Guard Kind</th>
                                <th style={{ padding: "6px", border: "1px solid #e1bee7" }}>Funds Impact</th>
                                <th style={{ padding: "6px", border: "1px solid #e1bee7" }}>Span Link</th>
                              </tr>
                            </thead>
                            <tbody>
                              {privData.actions
                                ?.filter((act: PrivilegedAction) => act.guard_roles?.includes(r.role_key))
                                .map((act: PrivilegedAction, idx: number) => (
                                  <tr key={idx}>
                                    <td style={{ padding: "6px", border: "1px solid #eee", fontFamily: "monospace", fontWeight: "bold" }}>
                                      {act.function_signature}
                                    </td>
                                    <td style={{ padding: "6px", border: "1px solid #eee" }}>
                                      {act.power_category}
                                    </td>
                                    <td style={{ padding: "6px", border: "1px solid #eee" }}>
                                      {act.guard_kind}
                                    </td>
                                    <td style={{ padding: "6px", border: "1px solid #eee" }}>
                                      {act.funds_impact}
                                    </td>
                                    <td style={{ padding: "6px", border: "1px solid #eee" }}>
                                      <Link
                                        href={`/files?audit_id=${auditId}`}
                                        style={{ color: "#0066cc", textDecoration: "underline", fontSize: "11px" }}
                                      >
                                        Jump to L{act.start_line}-L{act.end_line}
                                      </Link>
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>

          {/* Undetected Notes */}
          {privData.undetected_notes && privData.undetected_notes.length > 0 && (
            <div style={{ marginTop: "16px", padding: "12px", backgroundColor: "#fffbe6", border: "1px solid #ffe58f", borderRadius: "4px" }}>
              <h4 style={{ margin: "0 0 6px 0", color: "#d48806" }}>What this view cannot see (Undetected Notes):</h4>
              <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "13px" }}>
                {privData.undetected_notes.map((note: string, idx: number) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Role Declaration Form */}
          <div style={{ marginTop: "24px", padding: "16px", border: "1px solid #ddd", borderRadius: "4px", backgroundColor: "#f9f9f9" }}>
            <h3 style={{ margin: "0 0 12px 0" }}>Update Role-Holder Declaration (PUT /role-declarations)</h3>
            <form onSubmit={handleUpdateDeclaration} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ fontSize: "12px", display: "block" }}>Target Role:</label>
                <select
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  style={{ width: "100%", padding: "6px" }}
                >
                  {privData.results?.map((r) => (
                    <option key={r.role_key} value={r.role_key}>
                      {r.role_key} (current score: {r.blast_score})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: "12px", display: "block" }}>Holder Type:</label>
                <select
                  value={holderType}
                  onChange={(e) => setHolderType(e.target.value)}
                  style={{ width: "100%", padding: "6px" }}
                >
                  <option value="multisig">Multisig (M-of-N)</option>
                  <option value="timelock_multisig">Timelock Multisig (Delay + M-of-N)</option>
                  <option value="eoa">EOA (Single Key)</option>
                  <option value="renounced">Renounced (Zero address)</option>
                  <option value="unknown">Unknown contract</option>
                </select>
              </div>

              {holderType.includes("multisig") && (
                <div>
                  <label style={{ fontSize: "12px", display: "block" }}>Threshold / Signers:</label>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="number"
                      value={threshold}
                      onChange={(e) => setThreshold(Number(e.target.value))}
                      style={{ width: "60px", padding: "6px" }}
                      placeholder="M"
                    />
                    <span>of</span>
                    <input
                      type="number"
                      value={signers}
                      onChange={(e) => setSigners(Number(e.target.value))}
                      style={{ width: "60px", padding: "6px" }}
                      placeholder="N"
                    />
                  </div>
                </div>
              )}

              {holderType === "timelock_multisig" && (
                <div>
                  <label style={{ fontSize: "12px", display: "block" }}>Delay (seconds):</label>
                  <input
                    type="number"
                    value={delaySeconds}
                    onChange={(e) => setDelaySeconds(Number(e.target.value))}
                    style={{ width: "100%", padding: "6px" }}
                  />
                </div>
              )}

              <div style={{ gridColumn: "1 / -1", marginTop: "8px" }}>
                <button
                  type="submit"
                  style={{
                    padding: "8px 16px",
                    backgroundColor: "#8e44ad",
                    color: "#fff",
                    border: "none",
                    borderRadius: "4px",
                    fontWeight: "bold",
                    cursor: "pointer",
                  }}
                >
                  Submit Declaration & Recompute Score
                </button>
              </div>
            </form>

            {/* Declaration History / Before-After Score */}
            {declHistory.length > 0 && (
              <div style={{ marginTop: "16px", borderTop: "1px solid #ddd", paddingTop: "12px" }}>
                <h4 style={{ margin: "0 0 6px 0", fontSize: "12px" }}>Declaration History & Score Diffs:</h4>
                <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "12px" }}>
                  {declHistory.map((h, i) => (
                    <li key={i}>
                      [{h.timestamp}] Declared <strong>{h.role}</strong> as <strong>{h.holderType}</strong> &mdash; Previous Score: <code>{h.oldScore}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      <RawJsonViewer data={privData} title="Raw Privilege Map JSON" />
    </div>
  );
}


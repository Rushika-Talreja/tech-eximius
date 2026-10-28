"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { DisclaimerBox } from "../../components/DisclaimerBox";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { AuditItem, ProjectItem } from "../../types/backend";

export default function AuditsPage() {
  const { authMode, apiKey, addLogEntry } = useConsole();
  const [audits, setAudits] = useState<AuditItem[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  // Creation form state
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [uploadId, setUploadId] = useState("");
  const [solcVersion, setSolcVersion] = useState("0.8.20");
  const [featPrivilegeMap, setFeatPrivilegeMap] = useState(true);
  const [featFindings, setFeatFindings] = useState(true);
  const [featRag, setFeatRag] = useState(false);
  const [featPatches, setFeatPatches] = useState(false);
  const [retentionHours, setRetentionHours] = useState(24);

  // Role declaration form inputs
  const [includeRoleDecl, setIncludeRoleDecl] = useState(false);
  const [roleKey, setRoleKey] = useState("OWNER");
  const [holderType, setHolderType] = useState("multisig");
  const [multisigThreshold, setMultisigThreshold] = useState(2);
  const [multisigSigners, setMultisigSigners] = useState(3);

  // Inspect detail state
  const [selectedAudit, setSelectedAudit] = useState<AuditItem | null>(null);

  const fetchProjectsAndAudits = async () => {
    setLoading(true);
    setError(null);
    try {
      const projRes = await executeApiRequest("/projects", {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      const projItems = projRes.data?.items || [];
      setProjects(projItems);
      if (projItems.length > 0 && !selectedProjectId) {
        setSelectedProjectId(projItems[0].id);
      }

      const auditRes = await executeApiRequest("/audits", {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setAudits(auditRes.data?.items || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjectsAndAudits();
  }, [authMode]);

  const handleCreateAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const features: string[] = [];
    if (featPrivilegeMap) features.push("privilege_map");
    if (featFindings) features.push("findings");
    if (featRag) features.push("rag");
    if (featPatches) features.push("patches");

    const role_declarations: any[] = [];
    if (includeRoleDecl) {
      role_declarations.push({
        role_key: roleKey,
        holder_type: holderType,
        params: {
          threshold: multisigThreshold,
          signers: multisigSigners,
        },
      });
    }

    try {
      const res = await executeApiRequest(`/projects/${selectedProjectId}/audits`, {
        method: "POST",
        body: {
          upload_id: uploadId.trim(),
          options: {
            solc_version: solcVersion,
            features,
            retention_hours: Number(retentionHours),
          },
          role_declarations,
        },
        authMode,
        apiKey,
        onLog: addLogEntry,
      });

      alert(`Audit created! Audit ID: ${res.data?.audit_id}`);
      fetchProjectsAndAudits();
    } catch (err) {
      setError(err);
    }
  };

  const inspectAudit = async (id: string) => {
    setError(null);
    try {
      const res = await executeApiRequest<AuditItem>(`/audits/${id}`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setSelectedAudit(res.data);
    } catch (err) {
      setError(err);
    }
  };

  const handleCancel = async (id: string) => {
    setError(null);
    try {
      await executeApiRequest(`/audits/${id}/cancel`, {
        method: "POST",
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      inspectAudit(id);
      fetchProjectsAndAudits();
    } catch (err) {
      setError(err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Permanently delete/purge audit and all stored files?")) return;
    setError(null);
    try {
      await executeApiRequest(`/audits/${id}`, {
        method: "DELETE",
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      if (selectedAudit?.id === id) setSelectedAudit(null);
      fetchProjectsAndAudits();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <div>
      <h2>Audits Management</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>POST /projects/&#123;id&#125;/audits</code>, <code>GET /audits</code>, <code>GET /audits/&#123;id&#125;</code>, <code>POST /audits/&#123;id&#125;/cancel</code>, and <code>DELETE /audits/&#123;id&#125;</code>.
      </p>

      <ErrorDisplay error={error} />

      {/* Creation form */}
      <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa", marginBottom: "20px" }}>
        <h3 style={{ margin: "0 0 12px 0" }}>Create New Audit</h3>
        <form onSubmit={handleCreateAudit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div>
              <label style={{ fontSize: "12px", display: "block" }}>Project:</label>
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                style={{ width: "100%", padding: "6px" }}
                required
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.id})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: "12px", display: "block" }}>Upload ID (UUID):</label>
              <input
                type="text"
                value={uploadId}
                onChange={(e) => setUploadId(e.target.value)}
                placeholder="Upload UUID from Uploads screen"
                style={{ width: "100%", padding: "6px", fontFamily: "monospace" }}
                required
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", display: "block" }}>Solc Version:</label>
              <input
                type="text"
                value={solcVersion}
                onChange={(e) => setSolcVersion(e.target.value)}
                style={{ width: "100%", padding: "6px" }}
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", display: "block" }}>Retention (hours):</label>
              <input
                type="number"
                value={retentionHours}
                onChange={(e) => setRetentionHours(Number(e.target.value))}
                style={{ width: "100%", padding: "6px" }}
              />
            </div>
          </div>

          {/* Feature toggles */}
          <div style={{ marginTop: "12px" }}>
            <label style={{ fontSize: "12px", fontWeight: "bold", display: "block", marginBottom: "4px" }}>
              Features to Enable:
            </label>
            <div style={{ display: "flex", gap: "16px", fontSize: "13px" }}>
              <label>
                <input
                  type="checkbox"
                  checked={featPrivilegeMap}
                  onChange={(e) => setFeatPrivilegeMap(e.target.checked)}
                />{" "}
                privilege_map
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={featFindings}
                  onChange={(e) => setFeatFindings(e.target.checked)}
                />{" "}
                findings
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={featRag}
                  onChange={(e) => setFeatRag(e.target.checked)}
                />{" "}
                rag
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={featPatches}
                  onChange={(e) => setFeatPatches(e.target.checked)}
                />{" "}
                patches
              </label>
            </div>
          </div>

          {/* Optional Role Declaration */}
          <div style={{ marginTop: "12px", padding: "8px", border: "1px dashed #ccc", borderRadius: "4px" }}>
            <label style={{ fontSize: "12px", fontWeight: "bold" }}>
              <input
                type="checkbox"
                checked={includeRoleDecl}
                onChange={(e) => setIncludeRoleDecl(e.target.checked)}
              />{" "}
              Include Initial Role Declaration
            </label>

            {includeRoleDecl && (
              <div style={{ display: "flex", gap: "12px", marginTop: "8px", fontSize: "12px" }}>
                <div>
                  Role Key:{" "}
                  <input
                    type="text"
                    value={roleKey}
                    onChange={(e) => setRoleKey(e.target.value)}
                    style={{ width: "100px" }}
                  />
                </div>
                <div>
                  Holder Type:{" "}
                  <select value={holderType} onChange={(e) => setHolderType(e.target.value)}>
                    <option value="multisig">multisig</option>
                    <option value="eoa">eoa</option>
                    <option value="timelock_multisig">timelock_multisig</option>
                    <option value="renounced">renounced</option>
                  </select>
                </div>
                <div>
                  Threshold:{" "}
                  <input
                    type="number"
                    value={multisigThreshold}
                    onChange={(e) => setMultisigThreshold(Number(e.target.value))}
                    style={{ width: "60px" }}
                  />
                </div>
                <div>
                  Signers:{" "}
                  <input
                    type="number"
                    value={multisigSigners}
                    onChange={(e) => setMultisigSigners(Number(e.target.value))}
                    style={{ width: "60px" }}
                  />
                </div>
              </div>
            )}
          </div>

          <button
            type="submit"
            style={{
              marginTop: "16px",
              padding: "8px 16px",
              backgroundColor: "#27ae60",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              fontWeight: "bold",
              cursor: "pointer",
            }}
          >
            Submit Audit
          </button>
        </form>
      </div>

      {/* Audits table */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <h3 style={{ margin: 0 }}>Audit Runs ({audits.length})</h3>
        <button onClick={fetchProjectsAndAudits} disabled={loading} style={{ padding: "4px 8px" }}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ backgroundColor: "#f0f0f0", textAlign: "left" }}>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Audit ID</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Status</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Stage</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Created At</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "240px" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {audits.length === 0 ? (
            <tr>
              <td colSpan={5} style={{ padding: "12px", textAlign: "center", color: "#888" }}>
                No audits found for active identity.
              </td>
            </tr>
          ) : (
            audits.map((a) => (
              <tr key={a.id}>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace" }}>
                  {a.id.substring(0, 8)}...
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  <span
                    style={{
                      display: "inline-block",
                      padding: "2px 6px",
                      borderRadius: "3px",
                      color: "#fff",
                      fontWeight: "bold",
                      fontSize: "11px",
                      backgroundColor:
                        a.status === "complete"
                          ? "#27ae60"
                          : a.status === "running"
                          ? "#2980b9"
                          : a.status === "failed"
                          ? "#c0392b"
                          : a.status === "cancelled"
                          ? "#7f8c8d"
                          : "#e67e22",
                    }}
                  >
                    {a.status}
                  </span>
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace" }}>
                  {a.stage || "-"}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", color: "#666" }}>
                  {a.created_at}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  <button
                    onClick={() => inspectAudit(a.id)}
                    style={{ padding: "2px 6px", marginRight: "4px", cursor: "pointer" }}
                  >
                    Inspect
                  </button>
                  <Link
                    href={`/events?audit_id=${a.id}`}
                    style={{
                      display: "inline-block",
                      padding: "2px 6px",
                      marginRight: "4px",
                      textDecoration: "none",
                      backgroundColor: "#3498db",
                      color: "#fff",
                      borderRadius: "3px",
                      fontSize: "12px",
                    }}
                  >
                    SSE Events
                  </Link>
                  {a.status === "running" && (
                    <button
                      onClick={() => handleCancel(a.id)}
                      style={{ padding: "2px 6px", marginRight: "4px", backgroundColor: "#f39c12", color: "#fff", border: "none", borderRadius: "3px" }}
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(a.id)}
                    style={{ padding: "2px 6px", backgroundColor: "#e74c3c", color: "#fff", border: "none", borderRadius: "3px", cursor: "pointer" }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Selected Audit Detail View */}
      {selectedAudit && (
        <div style={{ marginTop: "24px", padding: "16px", border: "1px solid #34495e", borderRadius: "4px", backgroundColor: "#fdfefe" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>Audit Detail: {selectedAudit.id}</h3>
            <span style={{ fontSize: "12px", color: "#666" }}>Status: <strong>{selectedAudit.status}</strong></span>
          </div>

          <DisclaimerBox disclaimer={selectedAudit.disclaimer} />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "12px", fontSize: "13px", fontFamily: "monospace" }}>
            <div>Project ID: <strong>{selectedAudit.project_id}</strong></div>
            <div>Upload ID: <strong>{selectedAudit.upload_id}</strong></div>
            <div>Stage: <strong>{selectedAudit.stage || "(none)"}</strong></div>
            <div>Compiler: <strong>{selectedAudit.compiler_version || "(default)"}</strong></div>
            <div>Started At: <strong>{selectedAudit.started_at || "-"}</strong></div>
            <div>Finished At: <strong>{selectedAudit.finished_at || "-"}</strong></div>
            <div>Purge After: <strong>{selectedAudit.purge_after}</strong></div>
            <div>Purged At: <strong>{selectedAudit.purged_at || "Not purged"}</strong></div>
          </div>

          {selectedAudit.error && (
            <div style={{ marginTop: "12px", padding: "10px", backgroundColor: "#fdedec", border: "1px solid #fadbd8" }}>
              <strong style={{ color: "#c0392b" }}>Audit Error:</strong>
              <pre style={{ margin: "4px 0", fontSize: "12px" }}>
                {JSON.stringify(selectedAudit.error, null, 2)}
              </pre>
            </div>
          )}

          {selectedAudit.coverage && (
            <div style={{ marginTop: "12px", padding: "10px", backgroundColor: "#eafaf1", border: "1px solid #d5f5e3" }}>
              <strong style={{ color: "#27ae60" }}>Coverage Statement:</strong>
              <pre style={{ margin: "4px 0", fontSize: "12px" }}>
                {JSON.stringify(selectedAudit.coverage, null, 2)}
              </pre>
            </div>
          )}

          <div style={{ marginTop: "16px", display: "flex", gap: "10px" }}>
            <Link
              href={`/privilege-map?audit_id=${selectedAudit.id}`}
              style={{ padding: "6px 12px", backgroundColor: "#8e44ad", color: "#fff", textDecoration: "none", borderRadius: "3px", fontSize: "12px" }}
            >
              Open Privilege Map
            </Link>
            <Link
              href={`/findings?audit_id=${selectedAudit.id}`}
              style={{ padding: "6px 12px", backgroundColor: "#e67e22", color: "#fff", textDecoration: "none", borderRadius: "3px", fontSize: "12px" }}
            >
              Open Findings
            </Link>
            <Link
              href={`/files?audit_id=${selectedAudit.id}`}
              style={{ padding: "6px 12px", backgroundColor: "#2c3e50", color: "#fff", textDecoration: "none", borderRadius: "3px", fontSize: "12px" }}
            >
              Open Files
            </Link>
          </div>

          <RawJsonViewer data={selectedAudit} title="Raw Audit JSON" />
        </div>
      )}

      <RawJsonViewer data={audits} title="Raw Audits List JSON" />
    </div>
  );
}


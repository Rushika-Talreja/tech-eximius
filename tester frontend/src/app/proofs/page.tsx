"use client";

import React, { useState } from "react";
import { useSearchParams } from "next/navigation";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { ProofItem, InvariantItem } from "../../types/backend";

export default function ProofsPage() {
  const searchParams = useSearchParams();
  const initialAuditId = searchParams.get("audit_id") || "";

  const { authMode, apiKey, addLogEntry } = useConsole();
  const [auditId, setAuditId] = useState(initialAuditId);
  const [proofs, setProofs] = useState<ProofItem[]>([]);
  const [invariants, setInvariants] = useState<InvariantItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);
  const [featureDisabled, setFeatureDisabled] = useState(false);

  const fetchProofsAndInvariants = async () => {
    if (!auditId.trim()) {
      alert("Please enter an Audit ID");
      return;
    }
    setLoading(true);
    setError(null);
    setFeatureDisabled(false);

    try {
      const pRes = await executeApiRequest(`/audits/${auditId.trim()}/proofs`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setProofs(pRes.data?.items || []);
    } catch (err: any) {
      if (err.code === "FEATURE_NOT_ENABLED" || err.status === 422) {
        setFeatureDisabled(true);
      }
      setError(err);
    }

    try {
      const invRes = await executeApiRequest(`/audits/${auditId.trim()}/invariants`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setInvariants(invRes.data?.items || []);
    } catch (err: any) {
      if (err.code === "FEATURE_NOT_ENABLED" || err.status === 422) {
        setFeatureDisabled(true);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Proofs & Invariants (M6 & M7)</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>GET /audits/&#123;id&#125;/proofs</code> and <code>GET /audits/&#123;id&#125;/invariants</code>.
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
          onClick={fetchProofsAndInvariants}
          disabled={loading}
          style={{
            padding: "6px 14px",
            backgroundColor: "#2c3e50",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            fontWeight: "bold",
            cursor: "pointer",
          }}
        >
          {loading ? "Loading..." : "Fetch Proofs & Invariants"}
        </button>
      </div>

      {featureDisabled && (
        <div style={{ padding: "12px", backgroundColor: "#fff3cd", border: "1px solid #ffeeba", borderRadius: "4px", marginBottom: "16px", color: "#856404" }}>
          <strong>Feature Flag Notice:</strong> The backend reports this feature is currently disabled or feature-flagged for future milestones.
        </div>
      )}

      <ErrorDisplay error={error} />

      {/* Proofs Section */}
      <h3 style={{ margin: "20px 0 8px 0" }}>Exploit Proofs (M6)</h3>
      {proofs.length === 0 ? (
        <div style={{ fontSize: "12px", color: "#888" }}>No exploit proofs generated for this audit.</div>
      ) : (
        <div style={{ display: "grid", gap: "12px" }}>
          {proofs.map((p) => (
            <div key={p.id} style={{ border: "1px solid #ddd", padding: "12px", borderRadius: "4px" }}>
              <div style={{ fontWeight: "bold", marginBottom: "4px" }}>Proof #{p.id}</div>
              <div style={{ fontSize: "12px", marginBottom: "8px" }}>
                Fails on original: <strong>{p.fails_on_original ? "YES" : "NO"}</strong> |
                Passes on patched: <strong>{p.passes_on_patched ? "YES" : "NO"}</strong>
              </div>
              <pre style={{ backgroundColor: "#222", color: "#66ff66", padding: "10px", fontSize: "11px", overflowX: "auto" }}>
                {p.test_source}
              </pre>
            </div>
          ))}
        </div>
      )}

      {/* Invariants Section */}
      <h3 style={{ margin: "24px 0 8px 0" }}>Invariant Runs (M7)</h3>
      {invariants.length === 0 ? (
        <div style={{ fontSize: "12px", color: "#888" }}>No invariant runs recorded for this audit.</div>
      ) : (
        <div style={{ display: "grid", gap: "12px" }}>
          {invariants.map((inv) => (
            <div key={inv.id} style={{ border: "1px solid #ddd", padding: "12px", borderRadius: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: "bold" }}>Template: {inv.template_id}</span>
                <span style={{ fontWeight: "bold", color: inv.status === "passed" ? "#27ae60" : "#c0392b" }}>
                  Status: {inv.status.toUpperCase()}
                </span>
              </div>
              {inv.counterexample && (
                <div style={{ marginTop: "8px" }}>
                  <div style={{ fontSize: "11px", fontWeight: "bold" }}>Counterexample:</div>
                  <pre style={{ backgroundColor: "#fbfbfb", padding: "6px", fontSize: "11px" }}>
                    {JSON.stringify(inv.counterexample, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <RawJsonViewer data={{ proofs, invariants }} title="Raw Proofs & Invariants JSON" />
    </div>
  );
}


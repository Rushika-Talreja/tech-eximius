"use client";

import React, { useState } from "react";
import { useSearchParams } from "next/navigation";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { PatchItem } from "../../types/backend";

export default function PatchesPage() {
  const searchParams = useSearchParams();
  const initialAuditId = searchParams.get("audit_id") || "";
  const initialFindingId = searchParams.get("finding_id") || "";

  const { authMode, apiKey, addLogEntry } = useConsole();
  const [auditId, setAuditId] = useState(initialAuditId);
  const [findingId, setFindingId] = useState(initialFindingId);

  const [patch, setPatch] = useState<PatchItem | null>(null);
  const [editedDiff, setEditedDiff] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const generatePatch = async () => {
    if (!auditId.trim() || !findingId.trim()) {
      alert("Please provide both Audit UUID and Finding UUID");
      return;
    }
    setLoading(true);
    setError(null);
    setPatch(null);

    try {
      const res = await executeApiRequest<PatchItem>(
        `/audits/${auditId.trim()}/findings/${findingId.trim()}/patches`,
        {
          method: "POST",
          authMode,
          apiKey,
          onLog: addLogEntry,
        }
      );
      setPatch(res.data);
      setEditedDiff(res.data?.unified_diff || "");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const reverifyEditedDiff = async () => {
    if (!patch) return;
    setLoading(true);
    setError(null);

    try {
      const res = await executeApiRequest<PatchItem>(
        `/audits/${auditId.trim()}/findings/${findingId.trim()}/patches`,
        {
          method: "POST",
          body: {
            custom_diff: editedDiff,
            base_patch_id: patch.id,
          },
          authMode,
          apiKey,
          onLog: addLogEntry,
        }
      );
      setPatch(res.data);
      alert("Diff submitted for verification!");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const renderDiffLines = (diff: string) => {
    if (!diff) return null;
    return diff.split("\n").map((line, idx) => {
      let bg = "transparent";
      let color = "#333";
      if (line.startsWith("+") && !line.startsWith("+++")) {
        bg = "#e6ffed";
        color = "#22863a";
      } else if (line.startsWith("-") && !line.startsWith("---")) {
        bg = "#ffeef0";
        color = "#cb2431";
      } else if (line.startsWith("@@")) {
        bg = "#f1f8ff";
        color = "#0366d6";
      }

      return (
        <div key={idx} style={{ backgroundColor: bg, color, padding: "1px 6px", whiteSpace: "pre-wrap" }}>
          {line}
        </div>
      );
    });
  };

  return (
    <div>
      <h2>Automated Patches & Diff Verifier</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>POST /audits/&#123;id&#125;/findings/&#123;fid&#125;/patches</code> and reverification workflows.
      </p>

      {/* Inputs */}
      <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa", marginBottom: "20px" }}>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Audit ID:</label>
            <input
              type="text"
              value={auditId}
              onChange={(e) => setAuditId(e.target.value)}
              placeholder="Audit UUID"
              style={{ width: "260px", padding: "6px", fontFamily: "monospace" }}
            />
          </div>

          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Finding ID:</label>
            <input
              type="text"
              value={findingId}
              onChange={(e) => setFindingId(e.target.value)}
              placeholder="Finding UUID"
              style={{ width: "260px", padding: "6px", fontFamily: "monospace" }}
            />
          </div>

          <div style={{ marginTop: "16px" }}>
            <button
              onClick={generatePatch}
              disabled={loading}
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
              {loading ? "Generating..." : "Generate Patch"}
            </button>
          </div>
        </div>
      </div>

      <ErrorDisplay error={error} />

      {/* Patch Inspector */}
      {patch && (
        <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>Patch #{patch.version} &mdash; Status: {patch.status}</h3>
            <span style={{ fontSize: "12px", color: "#666" }}>Created: {patch.created_at}</span>
          </div>

          {/* Verification Status Badges */}
          <div style={{ display: "flex", gap: "8px", margin: "12px 0", flexWrap: "wrap" }}>
            <span
              style={{
                padding: "3px 8px",
                borderRadius: "3px",
                fontSize: "11px",
                fontWeight: "bold",
                backgroundColor: patch.compiles ? "#d4edda" : "#f8d7da",
                color: patch.compiles ? "#155724" : "#721c24",
                border: "1px solid",
              }}
            >
              Compiles: {patch.compiles ? "YES" : patch.compiles === false ? "NO" : "PENDING"}
            </span>

            <span
              style={{
                padding: "3px 8px",
                borderRadius: "3px",
                fontSize: "11px",
                fontWeight: "bold",
                backgroundColor: patch.finding_cleared ? "#d4edda" : "#f8d7da",
                color: patch.finding_cleared ? "#155724" : "#721c24",
                border: "1px solid",
              }}
            >
              Finding Cleared: {patch.finding_cleared ? "YES" : "NO"}
            </span>

            <span
              style={{
                padding: "3px 8px",
                borderRadius: "3px",
                fontSize: "11px",
                fontWeight: "bold",
                backgroundColor: patch.tests_passed ? "#d4edda" : "#f8d7da",
                color: patch.tests_passed ? "#155724" : "#721c24",
                border: "1px solid",
              }}
            >
              Tests Passed: {patch.tests_passed ? "PASS" : "FAIL/SKIP"}
            </span>
          </div>

          <p style={{ fontSize: "13px", color: "#444" }}>
            <strong>Rationale:</strong> {patch.rationale}
          </p>

          {/* Colored Diff Viewer */}
          <h4 style={{ margin: "16px 0 6px 0" }}>Unified Diff (Red/Green Viewer):</h4>
          <div
            style={{
              border: "1px solid #ddd",
              backgroundColor: "#fafafa",
              fontFamily: "monospace",
              fontSize: "12px",
              lineHeight: "1.4",
              overflowX: "auto",
              maxHeight: "350px",
              padding: "8px",
            }}
          >
            {renderDiffLines(patch.unified_diff)}
          </div>

          {/* Edit & Reverify Box */}
          <div style={{ marginTop: "20px", borderTop: "1px solid #eee", paddingTop: "16px" }}>
            <h4 style={{ margin: "0 0 8px 0" }}>Edit & Reverify Custom Diff:</h4>
            <textarea
              value={editedDiff}
              onChange={(e) => setEditedDiff(e.target.value)}
              rows={8}
              style={{ width: "100%", fontFamily: "monospace", fontSize: "12px", padding: "8px" }}
            />
            <div style={{ marginTop: "8px" }}>
              <button
                onClick={reverifyEditedDiff}
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
                Submit Edited Diff for Reverification
              </button>
            </div>
          </div>
        </div>
      )}

      <RawJsonViewer data={patch} title="Raw Patch JSON" />
    </div>
  );
}


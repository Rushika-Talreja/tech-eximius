"use client";

import React, { useEffect, useState } from "react";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { ApiKeyItem } from "../../types/backend";

export default function ApiKeysPage() {
  const { authMode, apiKey, addLogEntry, setApiKey, setAuthMode } = useConsole();
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  // Creation form state
  const [keyName, setKeyName] = useState("ci-test-key");
  const [scopes, setScopes] = useState("audits:write,audits:read");
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  // Last revoked key for negative testing
  const [lastRevokedKey, setLastRevokedKey] = useState<string | null>(null);
  const [retryResult, setRetryResult] = useState<any>(null);
  const [retryError, setRetryError] = useState<any>(null);

  const fetchKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await executeApiRequest("/api-keys", {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setKeys(res.data?.items || []);
    } catch (err) {
      setError(err);
      setKeys([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKeys();
  }, [authMode]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const scopeList = scopes.split(",").map((s) => s.trim()).filter(Boolean);
      const res = await executeApiRequest("/api-keys", {
        method: "POST",
        body: { name: keyName, scopes: scopeList },
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      if (res.data?.key) {
        setCreatedKey(res.data.key);
      }
      fetchKeys();
    } catch (err) {
      setError(err);
    }
  };

  const handleRevoke = async (id: string, prefix: string) => {
    if (!confirm(`Revoke key ${prefix}...?`)) return;
    setError(null);
    try {
      await executeApiRequest(`/api-keys/${id}`, {
        method: "DELETE",
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      // Save for retry test
      if (createdKey && createdKey.startsWith(prefix)) {
        setLastRevokedKey(createdKey);
      } else {
        setLastRevokedKey(prefix);
      }
      fetchKeys();
    } catch (err) {
      setError(err);
    }
  };

  const testWithRevokedKey = async () => {
    if (!lastRevokedKey) return;
    setRetryError(null);
    setRetryResult(null);
    try {
      const res = await executeApiRequest("/me", {
        authMode: "api_key",
        apiKey: lastRevokedKey,
        onLog: addLogEntry,
      });
      setRetryResult(res.data);
    } catch (err) {
      setRetryError(err);
    }
  };

  return (
    <div>
      <h2>API Keys Management</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>POST /api-keys</code>, <code>GET /api-keys</code>, and <code>DELETE /api-keys/&#123;id&#125;</code>.
      </p>

      <ErrorDisplay error={error} />

      {/* Creation Box */}
      <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa", marginBottom: "20px" }}>
        <h3 style={{ margin: "0 0 12px 0" }}>Create New API Key</h3>
        <form onSubmit={handleCreate} style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Key Name:</label>
            <input
              type="text"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              style={{ padding: "4px 8px" }}
              required
            />
          </div>
          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Scopes (comma-separated):</label>
            <input
              type="text"
              value={scopes}
              onChange={(e) => setScopes(e.target.value)}
              style={{ padding: "4px 8px", width: "240px" }}
              required
            />
          </div>
          <button
            type="submit"
            style={{
              marginTop: "16px",
              padding: "6px 14px",
              backgroundColor: "#27ae60",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            Create API Key
          </button>
        </form>

        {/* Revealed Key Banner */}
        {createdKey && (
          <div style={{ marginTop: "16px", padding: "12px", backgroundColor: "#e8f8f5", border: "1px solid #a3e4d7", borderRadius: "4px" }}>
            <div style={{ fontWeight: "bold", color: "#117864" }}>
              API Key Created (Shown Once):
            </div>
            <code style={{ fontSize: "14px", fontWeight: "bold", wordBreak: "break-all" }}>
              {createdKey}
            </code>
            <div style={{ marginTop: "8px" }}>
              <button
                onClick={() => {
                  setApiKey(createdKey);
                  setAuthMode("api_key");
                }}
                style={{ fontSize: "12px", padding: "3px 8px", cursor: "pointer" }}
              >
                Set As Active Header Key
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Keys List */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <h3 style={{ margin: 0 }}>Existing API Keys ({keys.length})</h3>
        <button onClick={fetchKeys} disabled={loading} style={{ padding: "4px 8px" }}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ backgroundColor: "#f0f0f0", textAlign: "left" }}>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Name</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Prefix</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Scopes</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Status</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Created At</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {keys.length === 0 ? (
            <tr>
              <td colSpan={6} style={{ padding: "12px", textAlign: "center", color: "#888" }}>
                No API keys found for active identity.
              </td>
            </tr>
          ) : (
            keys.map((k) => (
              <tr key={k.id} style={{ backgroundColor: k.revoked_at ? "#fcfcfc" : "#fff" }}>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontWeight: "bold" }}>
                  {k.name}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace" }}>
                  {k.key_prefix}...
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  {Array.isArray(k.scopes) ? k.scopes.join(", ") : String(k.scopes)}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  {k.revoked_at ? (
                    <span style={{ color: "#c0392b", fontWeight: "bold" }}>Revoked</span>
                  ) : (
                    <span style={{ color: "#27ae60", fontWeight: "bold" }}>Active</span>
                  )}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", color: "#666" }}>
                  {k.created_at}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  {!k.revoked_at && (
                    <button
                      onClick={() => handleRevoke(k.id, k.key_prefix)}
                      style={{
                        padding: "2px 8px",
                        backgroundColor: "#e74c3c",
                        color: "#fff",
                        border: "none",
                        borderRadius: "3px",
                        cursor: "pointer",
                      }}
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Negative Testing: Test with Revoked Key */}
      <div style={{ marginTop: "24px", padding: "16px", border: "1px solid #f5b7b1", borderRadius: "4px", backgroundColor: "#fdf2e9" }}>
        <h4 style={{ margin: "0 0 8px 0", color: "#b9770e" }}>
          Negative Test: Retry with Revoked Key
        </h4>
        <p style={{ margin: "0 0 10px 0", fontSize: "12px", color: "#555" }}>
          Target key for test: <code>{lastRevokedKey || "(revoked key will appear here after revoking above)"}</code>
        </p>
        <button
          onClick={testWithRevokedKey}
          disabled={!lastRevokedKey}
          style={{
            padding: "6px 12px",
            backgroundColor: "#d35400",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: lastRevokedKey ? "pointer" : "not-allowed",
          }}
        >
          Call GET /me With Revoked Key (Expect 401)
        </button>

        <ErrorDisplay error={retryError} />
        {retryResult && (
          <div style={{ color: "#c0392b", marginTop: "8px", fontWeight: "bold" }}>
            Unexpected success: key was accepted!
          </div>
        )}
      </div>

      <RawJsonViewer data={keys} title="Raw API Keys Response" />
    </div>
  );
}


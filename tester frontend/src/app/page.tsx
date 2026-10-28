"use client";

import React, { useEffect, useState } from "react";
import { executeApiRequest } from "../lib/api";
import { useConsole } from "../lib/store";
import { NotImplementedBadge } from "../components/NotImplementedBadge";
import { RawJsonViewer } from "../components/RawJsonViewer";

interface RouteInfo {
  method: string;
  path: string;
  summary?: string;
  status?: "OK" | "NOT_IMPLEMENTED" | "ERROR" | "UNTESTED";
  statusCode?: number;
  latency?: number;
}

const DEFAULT_ROUTES: RouteInfo[] = [
  { method: "GET", path: "/health", summary: "Health probe" },
  { method: "GET", path: "/me", summary: "Current user and org info" },
  { method: "GET", path: "/api-keys", summary: "List API keys" },
  { method: "POST", path: "/api-keys", summary: "Create an API key" },
  { method: "DELETE", path: "/api-keys/{id}", summary: "Revoke API key" },
  { method: "GET", path: "/projects", summary: "List projects" },
  { method: "POST", path: "/projects", summary: "Create project" },
  { method: "GET", path: "/projects/{id}", summary: "Get project details" },
  { method: "DELETE", path: "/projects/{id}", summary: "Delete project" },
  { method: "POST", path: "/uploads", summary: "Upload smart contract or zip" },
  { method: "POST", path: "/projects/{id}/audits", summary: "Enqueue new audit" },
  { method: "GET", path: "/audits", summary: "List audits" },
  { method: "GET", path: "/audits/{id}", summary: "Get audit summary" },
  { method: "DELETE", path: "/audits/{id}", summary: "Purge audit and storage" },
  { method: "POST", path: "/audits/{id}/cancel", summary: "Cancel running audit" },
  { method: "GET", path: "/audits/{id}/events", summary: "SSE live event stream" },
  { method: "GET", path: "/audits/{id}/files", summary: "List audit files" },
  { method: "GET", path: "/audits/{id}/files/{fid}", summary: "Get file content" },
  { method: "GET", path: "/audits/{id}/privilege-map", summary: "Flagship Privilege Map graph & table" },
  { method: "GET", path: "/audits/{id}/role-declarations", summary: "Get role declarations" },
  { method: "PUT", path: "/audits/{id}/role-declarations", summary: "Update role declarations & recompute" },
  { method: "GET", path: "/audits/{id}/findings", summary: "List findings with evidence" },
  { method: "GET", path: "/audits/{id}/findings/{fid}", summary: "Get finding details" },
  { method: "PATCH", path: "/audits/{id}/findings/{fid}", summary: "Dismiss/reopen finding" },
  { method: "POST", path: "/audits/{id}/findings/{fid}/patches", summary: "Generate patch" },
  { method: "GET", path: "/patches/{id}", summary: "Get patch details" },
  { method: "GET", path: "/audits/{id}/proofs", summary: "Get proofs (M6)" },
  { method: "GET", path: "/audits/{id}/invariants", summary: "Get invariant runs (M7)" },
  { method: "GET", path: "/audits/{id}/report", summary: "Get report summary" },
  { method: "GET", path: "/audits/{id}/export", summary: "Export report (JSON/MD/SARIF)" },
  { method: "GET", path: "/corpus/versions", summary: "List corpus versions" },
];

export default function CatalogPage() {
  const { authMode, apiKey, addLogEntry } = useConsole();
  const [routes, setRoutes] = useState<RouteInfo[]>(DEFAULT_ROUTES);
  const [isPinging, setIsPinging] = useState(false);
  const [openapiData, setOpenapiData] = useState<any>(null);

  useEffect(() => {
    // Fetch live openapi.json to verify backend schema
    executeApiRequest("/openapi.json", { authMode: "none", onLog: addLogEntry })
      .then((res) => {
        setOpenapiData(res.data);
      })
      .catch(() => {
        // Backend not yet reachable or openapi at root
      });
  }, []);

  const pingAllRoutes = async () => {
    setIsPinging(true);
    const updated = [...routes];

    for (let i = 0; i < updated.length; i++) {
      const r = updated[i];
      // Skip routes with parameter placeholders for batch ping, or test with dummy UUID
      let testPath = r.path
        .replace("{id}", "00000000-0000-0000-0000-000000000000")
        .replace("{fid}", "00000000-0000-0000-0000-000000000000");

      if (r.method === "GET") {
        try {
          const res = await executeApiRequest(testPath, {
            authMode,
            apiKey,
            onLog: addLogEntry,
          });
          r.status = "OK";
          r.statusCode = res.status;
          r.latency = res.durationMs;
        } catch (err: any) {
          r.statusCode = err.status || 0;
          if (err.isNotImplemented) {
            r.status = "NOT_IMPLEMENTED";
          } else if (err.status === 404 && r.path.includes("{id}")) {
            // 404 on dummy UUID still indicates route handler exists!
            r.status = "OK";
          } else if (err.status === 401 || err.status === 403) {
            r.status = "OK"; // route exists, auth enforced
          } else {
            r.status = "ERROR";
          }
        }
      } else {
        r.status = "UNTESTED";
      }
      setRoutes([...updated]);
    }
    setIsPinging(false);
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0" }}>Backend OpenAPI Route Catalog</h2>
          <p style={{ margin: 0, color: "#666", fontSize: "14px" }}>
            Live status of all documented and implemented endpoints.
          </p>
        </div>
        <button
          onClick={pingAllRoutes}
          disabled={isPinging}
          style={{
            padding: "8px 16px",
            backgroundColor: "#0066cc",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            fontWeight: "bold",
            cursor: isPinging ? "not-allowed" : "pointer",
          }}
        >
          {isPinging ? "Pinging Endpoints..." : "Ping GET Endpoints"}
        </button>
      </div>

      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          marginTop: "16px",
          fontSize: "13px",
        }}
      >
        <thead>
          <tr style={{ backgroundColor: "#f0f0f0", textAlign: "left" }}>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Method</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Path</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Summary</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "160px" }}>Status</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "100px" }}>Latency</th>
          </tr>
        </thead>
        <tbody>
          {routes.map((r, i) => (
            <tr key={i} style={{ backgroundColor: i % 2 === 0 ? "#fff" : "#fafafa" }}>
              <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace", fontWeight: "bold" }}>
                {r.method}
              </td>
              <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace" }}>
                {r.path}
              </td>
              <td style={{ padding: "6px 8px", border: "1px solid #ddd", color: "#555" }}>
                {r.summary}
              </td>
              <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                {r.status === "OK" && (
                  <span style={{ color: "#27ae60", fontWeight: "bold" }}>● OK ({r.statusCode})</span>
                )}
                {r.status === "NOT_IMPLEMENTED" && <NotImplementedBadge />}
                {r.status === "ERROR" && (
                  <span style={{ color: "#c0392b", fontWeight: "bold" }}>✕ ERROR ({r.statusCode})</span>
                )}
                {(!r.status || r.status === "UNTESTED") && (
                  <span style={{ color: "#999" }}>○ Untested</span>
                )}
              </td>
              <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontFamily: "monospace", color: "#666" }}>
                {r.latency !== undefined ? `${r.latency}ms` : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <RawJsonViewer data={openapiData} title="Raw OpenAPI Schema (/openapi.json)" />
    </div>
  );
}


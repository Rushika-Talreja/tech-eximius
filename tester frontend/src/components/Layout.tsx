"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useConsole, AuthMode } from "../lib/store";
import { RequestLogDrawer } from "./RequestLogDrawer";

const NAV_ITEMS = [
  { href: "/", label: "API Catalog & Status" },
  { href: "/health", label: "Health & Identity" },
  { href: "/api-keys", label: "API Keys" },
  { href: "/projects", label: "Projects" },
  { href: "/uploads", label: "Uploads (Test Zips)" },
  { href: "/audits", label: "Audits" },
  { href: "/events", label: "Live Progress (SSE)" },
  { href: "/files", label: "Files & Code Viewer" },
  { href: "/privilege-map", label: "Privilege Map" },
  { href: "/findings", label: "Findings" },
  { href: "/patches", label: "Patches" },
  { href: "/proofs", label: "Proofs & Invariants" },
  { href: "/exports", label: "Exports" },
  { href: "/corpus", label: "Corpus" },
  { href: "/checks", label: "★ Run All Checks" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { authMode, setAuthMode, apiKey, setApiKey, showRawJson, setShowRawJson } = useConsole();

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", fontFamily: "sans-serif" }}>
      {/* Red Alert Banner */}
      <div
        style={{
          backgroundColor: "#d9534f",
          color: "#fff",
          padding: "6px 16px",
          textAlign: "center",
          fontWeight: "bold",
          fontSize: "13px",
          letterSpacing: "1px",
        }}
      >
        ⚠️ TEMPORARY TEST CONSOLE &mdash; INTERNAL BACKEND INSPECTION ONLY
      </div>

      {/* Top Header / Auth Panel */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px 16px",
          backgroundColor: "#f4f4f4",
          borderBottom: "1px solid #ccc",
          fontSize: "13px",
        }}
      >
        <div style={{ fontWeight: "bold" }}>
          <Link href="/" style={{ textDecoration: "none", color: "#333" }}>
            DeFi Auditor Test Console
          </Link>
        </div>

        {/* Auth identity switcher */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span><strong>Active Identity:</strong></span>
          <select
            value={authMode}
            onChange={(e) => setAuthMode(e.target.value as AuthMode)}
            style={{ padding: "4px 8px", fontSize: "13px" }}
          >
            <option value="user_a">User A (Org A - Bearer dev-token-a)</option>
            <option value="user_b">User B (Org B - Bearer dev-token-b)</option>
            <option value="api_key">API Key Mode (X-API-Key)</option>
            <option value="none">Unauthenticated (None)</option>
          </select>

          {authMode === "api_key" && (
            <input
              type="text"
              placeholder="Enter ak_live_..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              style={{ padding: "4px 8px", width: "220px", fontFamily: "monospace", fontSize: "12px" }}
            />
          )}

          <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer", marginLeft: "12px" }}>
            <input
              type="checkbox"
              checked={showRawJson}
              onChange={(e) => setShowRawJson(e.target.checked)}
            />
            <span>Show Raw JSON Everywhere</span>
          </label>
        </div>
      </div>

      {/* Main Workspace: Left Nav + Content */}
      <div style={{ display: "flex", flex: 1, paddingBottom: "50px" }}>
        {/* Left Nav */}
        <nav
          style={{
            width: "220px",
            backgroundColor: "#fbfbfb",
            borderRight: "1px solid #ddd",
            padding: "12px 0",
            flexShrink: 0,
          }}
        >
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    style={{
                      display: "block",
                      padding: "8px 16px",
                      textDecoration: "none",
                      color: active ? "#0066cc" : "#333",
                      backgroundColor: active ? "#eef6ff" : "transparent",
                      fontWeight: active ? "bold" : "normal",
                      fontSize: "13px",
                      borderLeft: active ? "4px solid #0066cc" : "4px solid transparent",
                    }}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Main Content Area */}
        <main style={{ flex: 1, padding: "20px 28px", overflowX: "auto" }}>
          {children}
        </main>
      </div>

      {/* Persistent Bottom Request Log Drawer */}
      <RequestLogDrawer />
    </div>
  );
}


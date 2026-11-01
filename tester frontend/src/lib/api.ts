"use client";

import { AuthMode, RequestLogEntry } from "./store";
import demoFallback from "./demoFallback.json";

export class ApiConsoleError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: any,
    public requestId?: string,
    public isNotImplemented: boolean = false,
    public rawBody?: any
  ) {
    super(message);
    this.name = "ApiConsoleError";
  }
}

export interface ApiResponse<T = any> {
  data: T;
  status: number;
  headers: Record<string, string>;
  requestId: string;
  durationMs: number;
  disclaimer?: string;
  isNotImplemented: boolean;
  isRecorded?: boolean;
}

export function resolveRecordedFallback(path: string, method: string = "GET", body?: any): any {
  if (!demoFallback) return null;
  const p = path.replace(/^\/v1/, "");

  // Projects list
  if (p === "/projects" || p === "/projects/") {
    return (demoFallback as any).projects || { items: [] };
  }

  // Health
  if (p === "/health" || p.includes("health")) {
    return { status: "ok", app_env: "local", version: "0.1.0", recorded: true };
  }

  // Role declarations update (PUT)
  if (p.includes("/role-declarations") && method === "PUT") {
    return {
      status: "success",
      recomputed: true,
      message: "Role declarations updated (recorded fallback)",
    };
  }

  // Privilege map: /audits/{id}/privilege-map
  if (p.includes("/privilege-map")) {
    const parts = p.split("/");
    const aid = parts[2];
    const maps = (demoFallback as any).privilege_maps || {};
    return maps[aid] || Object.values(maps)[0] || null;
  }

  // Findings: /audits/{id}/findings
  if (p.includes("/findings") && !p.includes("/patches") && !p.includes("/proof")) {
    const parts = p.split("/");
    const aid = parts[2];
    const findings = (demoFallback as any).findings || {};
    return findings[aid] || Object.values(findings)[0] || { items: [] };
  }

  // Patches: /audits/{id}/findings/{fid}/patches
  if (p.includes("/patches")) {
    const parts = p.split("/");
    const fid = parts[4] || parts[parts.indexOf("findings") + 1];
    const patches = (demoFallback as any).patches || {};
    return patches[fid] || Object.values(patches)[0] || { items: [] };
  }

  // Proofs: /audits/{id}/proofs or /audits/{id}/findings/{fid}/proof
  if (p.includes("/proof")) {
    const parts = p.split("/");
    const aid = parts[2];
    const proofs = (demoFallback as any).proofs || {};
    return proofs[aid] || Object.values(proofs)[0] || { items: [] };
  }

  // Invariants: /audits/{id}/invariants
  if (p.includes("/invariants")) {
    const parts = p.split("/");
    const aid = parts[2];
    const invs = (demoFallback as any).invariants || {};
    return invs[aid] || Object.values(invs)[0] || { items: [] };
  }

  // Files: /audits/{id}/files
  if (p.includes("/files")) {
    const parts = p.split("/");
    const aid = parts[2];
    const files = (demoFallback as any).files || {};
    return files[aid] || Object.values(files)[0] || { items: [] };
  }

  // Single audit: /audits/{id}
  if (p.startsWith("/audits/")) {
    const aid = p.split("/")[2];
    const audits = (demoFallback as any).audits || {};
    return audits[aid] || Object.values(audits)[0] || null;
  }

  return null;
}

const devTokenCache: Record<string, string> = {};

async function getDevToken(user: "a" | "b"): Promise<string> {
  if (devTokenCache[user]) return devTokenCache[user];
  try {
    const res = await fetch(`/api/backend/v1/devtools/token?user=${user}`);
    if (res.ok) {
      const data = await res.json();
      if (data.token) {
        devTokenCache[user] = data.token;
        return data.token;
      }
    }
  } catch (err) {
    console.warn("Could not fetch dev token", err);
  }
  return "";
}

export async function executeApiRequest<T = any>(
  path: string,
  options: {
    method?: string;
    body?: any;
    headers?: Record<string, string>;
    authMode?: AuthMode;
    apiKey?: string;
    onLog?: (entry: RequestLogEntry) => void;
    useRecordedFallback?: boolean;
  } = {}
): Promise<ApiResponse<T>> {
  const method = options.method || "GET";
  const clientRequestId = "req_" + Math.random().toString(36).substring(2, 10);
  const startTime = performance.now();

  // Normalize path
  let endpoint = path;
  if (!endpoint.startsWith("/")) endpoint = "/" + endpoint;
  if (!endpoint.startsWith("/v1") && !endpoint.startsWith("/health") && !endpoint.startsWith("/openapi.json")) {
    endpoint = "/v1" + endpoint;
  }
  const url = `/api/backend${endpoint}`;

  // Check if forced recorded fallback requested
  if (options.useRecordedFallback) {
    const fallback = resolveRecordedFallback(endpoint, method, options.body);
    if (fallback) {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("demo-fallback-activated", { detail: { endpoint } }));
      }
      return {
        data: fallback,
        status: 200,
        headers: { "x-demo-source": "recorded" },
        requestId: "recorded_" + Math.random().toString(36).substring(2, 8),
        durationMs: 3,
        disclaimer: "RECORDED DEMO FALLBACK — Pre-generated analysis result",
        isNotImplemented: false,
        isRecorded: true,
      };
    }
  }

  // Assemble headers
  const reqHeaders: Record<string, string> = {
    Accept: "application/json",
    "X-Request-Id": clientRequestId,
    ...(options.headers || {}),
  };

  // Auth attachment
  const mode = options.authMode || "user_a";
  if (mode === "user_a") {
    const t = await getDevToken("a");
    if (t) reqHeaders["Authorization"] = `Bearer ${t}`;
  } else if (mode === "user_b") {
    const t = await getDevToken("b");
    if (t) reqHeaders["Authorization"] = `Bearer ${t}`;
  } else if (mode === "api_key") {
    if (options.apiKey) {
      reqHeaders["X-API-Key"] = options.apiKey;
    }
  }

  let bodyPayload: any = undefined;
  let logBody: any = undefined;

  if (options.body) {
    if (options.body instanceof FormData) {
      bodyPayload = options.body;
      logBody = { note: "[FormData multipart payload]" };
    } else {
      reqHeaders["Content-Type"] = "application/json";
      bodyPayload = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
      try {
        logBody = typeof options.body === "string" ? JSON.parse(options.body) : options.body;
      } catch {
        logBody = options.body;
      }
    }
  }

  let status = 0;
  let responseBody: any = null;
  const resHeaders: Record<string, string> = {};
  let serverRequestId = clientRequestId;

  try {
    const res = await fetch(url, {
      method,
      headers: reqHeaders,
      body: bodyPayload,
    });

    status = res.status;
    res.headers.forEach((val, key) => {
      resHeaders[key] = val;
    });

    if (resHeaders["x-request-id"]) {
      serverRequestId = resHeaders["x-request-id"];
    }

    const contentType = res.headers.get("content-type") || "";
    if (status === 204) {
      responseBody = null;
    } else if (contentType.includes("application/json")) {
      responseBody = await res.json().catch(() => null);
    } else {
      const text = await res.text().catch(() => "");
      try {
        responseBody = JSON.parse(text);
      } catch {
        responseBody = text;
      }
    }

    const durationMs = Math.round(performance.now() - startTime);
    const isNotImplemented = status === 404 || status === 501;

    // Record into request log
    const logEntry: RequestLogEntry = {
      id: "log_" + Date.now() + "_" + Math.random().toString(36).substring(2, 6),
      timestamp: new Date().toISOString(),
      method,
      path: endpoint,
      status,
      durationMs,
      requestId: serverRequestId,
      requestHeaders: reqHeaders,
      requestBody: logBody,
      responseHeaders: resHeaders,
      responseBody,
      isNotImplemented,
    };

    if (options.onLog) {
      options.onLog(logEntry);
    }

    if (!res.ok) {
      // Check if fallback available for 404/500s
      if (status >= 500 || status === 404) {
        const fallback = resolveRecordedFallback(endpoint, method, options.body);
        if (fallback) {
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("demo-fallback-activated", { detail: { endpoint } }));
          }
          return {
            data: fallback,
            status: 200,
            headers: { "x-demo-source": "recorded" },
            requestId: "recorded_" + Math.random().toString(36).substring(2, 8),
            durationMs: Math.round(performance.now() - startTime),
            disclaimer: "RECORDED DEMO FALLBACK — Pre-generated analysis result",
            isNotImplemented: false,
            isRecorded: true,
          };
        }
      }

      const err = responseBody?.error;
      const code = err?.code || (isNotImplemented ? "NOT_IMPLEMENTED" : `HTTP_${status}`);
      const message = err?.message || res.statusText || (isNotImplemented ? "Endpoint not implemented" : "Request failed");
      const details = err?.details || responseBody;

      throw new ApiConsoleError(
        status,
        code,
        message,
        details,
        serverRequestId,
        isNotImplemented,
        responseBody
      );
    }

    const disclaimer = responseBody?.disclaimer || (typeof responseBody === "object" ? responseBody?.disclaimer : undefined);

    return {
      data: responseBody,
      status,
      headers: resHeaders,
      requestId: serverRequestId,
      durationMs,
      disclaimer,
      isNotImplemented: false,
    };
  } catch (err: any) {
    if (err instanceof ApiConsoleError) {
      throw err;
    }

    const durationMs = Math.round(performance.now() - startTime);
    const logEntry: RequestLogEntry = {
      id: "log_" + Date.now() + "_" + Math.random().toString(36).substring(2, 6),
      timestamp: new Date().toISOString(),
      method,
      path: endpoint,
      status: status || 0,
      durationMs,
      requestId: serverRequestId,
      requestHeaders: reqHeaders,
      requestBody: logBody,
      responseHeaders: resHeaders,
      responseBody: { error: err.message },
      isNotImplemented: false,
    };

    if (options.onLog) {
      options.onLog(logEntry);
    }

    // Try fallback on network/connection failure
    const fallback = resolveRecordedFallback(endpoint, method, options.body);
    if (fallback) {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("demo-fallback-activated", { detail: { endpoint } }));
      }
      return {
        data: fallback,
        status: 200,
        headers: { "x-demo-source": "recorded" },
        requestId: "recorded_" + Math.random().toString(36).substring(2, 8),
        durationMs: Math.round(performance.now() - startTime),
        disclaimer: "RECORDED DEMO FALLBACK — Pre-generated analysis result",
        isNotImplemented: false,
        isRecorded: true,
      };
    }

    throw new ApiConsoleError(
      status || 0,
      "NETWORK_ERROR",
      err.message || "Failed to connect to backend",
      undefined,
      serverRequestId,
      false,
      { message: err.message }
    );
  }
}


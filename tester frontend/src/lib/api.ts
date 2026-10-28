"use client";

import { AuthMode, RequestLogEntry } from "./store";

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


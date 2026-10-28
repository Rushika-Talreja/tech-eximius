# API Calls: How the Frontend Talks to the Backend

## 1. Principles

- Types come from OpenAPI via `openapi-typescript` (`make gen-types` writes `apps/web/src/lib/api/schema.d.ts`). Never hand-write API payload types.
- All requests go through one wrapper, `apiFetch`, which attaches auth, request IDs and normalizes errors.
- Server state lives in TanStack Query. Components never call `fetch` directly.
- Never log request/response bodies that contain source code.

## 2. Auth Headers

| Context | Header | Source |
|---|---|---|
| Dashboard (browser) | `Authorization: Bearer <access_token>` | OIDC session (token obtained server-side, passed through a Next.js route handler or session helper) |
| CI / scripts | `X-API-Key: ak_live_...` | Created in Settings, shown once |

Token handling: store the session in an httpOnly cookie managed by the auth library; the browser calls the backend through either (a) the token exposed to client code in memory only, or (b) a Next.js proxy route `/api/proxy/[...path]` that attaches the token server-side. **Preferred: option (b)**, so tokens never reach client JS and CORS is avoided.

## 3. `apiFetch` Wrapper

```ts
// apps/web/src/lib/api/client.ts
export class ApiError extends Error {
  constructor(public status: number, public code: string,
              message: string, public details?: unknown, public requestId?: string) { super(message); }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const requestId = crypto.randomUUID();
  const res = await fetch(`/api/proxy/v1${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      "X-Request-Id": requestId,
      ...init.headers,
    },
    credentials: "same-origin",
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const e = body?.error;
    throw new ApiError(res.status, e?.code ?? "INTERNAL", e?.message ?? res.statusText, e?.details, e?.request_id ?? requestId);
  }
  return body as T;
}
```

Global handling: `401` redirects to `/login`; `429` shows a toast with `Retry-After`; `410 AUDIT_PURGED` shows a "this audit was deleted per retention policy" state; `5xx` shows a retry UI with the `request_id`.

## 4. Query Keys and Hooks

```ts
export const qk = {
  me: ["me"] as const,
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  audits: (projectId: string) => ["audits", { projectId }] as const,
  audit: (id: string) => ["audit", id] as const,
  files: (id: string) => ["audit", id, "files"] as const,
  file: (id: string, fileId: string) => ["audit", id, "file", fileId] as const,
  privMap: (id: string) => ["audit", id, "privilege-map"] as const,
  findings: (id: string, f?: object) => ["audit", id, "findings", f ?? {}] as const,
  finding: (id: string, fid: string) => ["audit", id, "finding", fid] as const,
  patch: (pid: string) => ["patch", pid] as const,
};
```

| Hook | Call | Notes |
|---|---|---|
| `useMe()` | `GET /me` | staleTime 5 min |
| `useProjects()` | `GET /projects` | |
| `useCreateAudit()` | `POST /projects/{id}/audits` | on success navigate to `/audits/{id}` and start SSE |
| `useAudit(id)` | `GET /audits/{id}` | refetch on SSE terminal event; poll 3 s as fallback while `queued/running` |
| `usePrivilegeMap(id)` | `GET /audits/{id}/privilege-map` | enabled when stage past `privilege_map` or status `complete` |
| `useSaveDeclarations(id)` | `PUT /audits/{id}/role-declarations` | **optimistic**: debounce 400 ms, write response into `qk.privMap` cache |
| `useFindings(id, filters)` | `GET /audits/{id}/findings` | |
| `useFinding(id, fid)` | `GET .../findings/{fid}` | |
| `useDismissFinding()` | `PATCH .../findings/{fid}` | invalidate findings list |
| `useGeneratePatch()` | `POST .../patches` | result via SSE `patch_ready` then invalidate `qk.patch` |
| `useVerifyPatch()` | `POST /patches/{pid}/verify` | |

## 5. Upload Flow

```ts
export async function uploadSource(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return apiFetch<{ upload_id: string }>("/uploads", { method: "POST", body: fd }); // no manual Content-Type
}
```
Client-side pre-checks: extension `.sol|.zip`, size under limit, show progress using `XMLHttpRequest` if upload progress is needed. Then create the audit with the returned `upload_id` (and optional `role_declarations`).

## 6. Live Progress (SSE)

`EventSource` cannot send custom headers, so use `@microsoft/fetch-event-source` through the proxy route (or rely on the cookie-authenticated proxy with plain `EventSource` if same-origin).

```ts
// hooks/useAuditEvents.ts
export function useAuditEvents(auditId: string, enabled: boolean) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    const ctrl = new AbortController();
    fetchEventSource(`/api/proxy/v1/audits/${auditId}/events`, {
      signal: ctrl.signal,
      openWhenHidden: true,
      onmessage(ev) {
        const data = JSON.parse(ev.data);
        switch (ev.event) {
          case "stage_completed":
          case "privilege_map_ready":
            qc.invalidateQueries({ queryKey: qk.audit(auditId) });
            if (ev.event === "privilege_map_ready") qc.invalidateQueries({ queryKey: qk.privMap(auditId) });
            break;
          case "finding_added": qc.invalidateQueries({ queryKey: ["audit", auditId, "findings"] }); break;
          case "patch_ready":   qc.invalidateQueries({ queryKey: ["patch"] }); break;
          case "audit_completed":
          case "audit_failed":  qc.invalidateQueries({ queryKey: qk.audit(auditId) }); ctrl.abort(); break;
        }
        useEventLog.getState().push(ev.event, data); // Zustand log for the progress panel
      },
      onerror(err) { /* library retries with Last-Event-ID; throw to stop on 4xx */ },
    });
    return () => ctrl.abort();
  }, [auditId, enabled, qc]);
}
```

Fallback: if SSE fails 3 times, switch to 3 s polling of `GET /audits/{id}`.

## 7. Next.js Proxy Route

`apps/web/src/app/api/proxy/[...path]/route.ts`:
- Reads the session, attaches `Authorization: Bearer ...`.
- Streams request/response bodies (needed for uploads and SSE); does not buffer.
- Forwards only an allowlist of headers; strips cookies from the upstream request.
- Rejects non-`/v1/` paths.
- Adds `X-Request-Id` if missing.

## 8. CI Usage (API key) Example

```bash
UP=$(curl -s -H "X-API-Key: $AK" -F file=@contracts.zip $API/v1/uploads | jq -r .upload_id)
AU=$(curl -s -H "X-API-Key: $AK" -H "Content-Type: application/json" \
  -d "{\"upload_id\":\"$UP\"}" $API/v1/projects/$PID/audits | jq -r .audit_id)
until [ "$(curl -s -H "X-API-Key: $AK" $API/v1/audits/$AU | jq -r .status)" = "complete" ]; do sleep 3; done
curl -s -H "X-API-Key: $AK" "$API/v1/audits/$AU/export?format=sarif" -o results.sarif
```

## 9. Error UX Mapping

| Code | UI behavior |
|---|---|
| `BUILD_FAILED` | Audit page shows compiler diagnostics list (file:line, message) with "fix and re-upload" |
| `UNSUPPORTED_SOURCE` | Inline upload error |
| `AUDIT_NOT_READY` | Show skeleton / progress, keep SSE open |
| `AUDIT_PURGED` | Empty state explaining retention |
| `RATE_LIMITED` | Toast with retry time |
| `OUT_OF_SCOPE` | Explain product scope (pre-deployment source analysis only) |

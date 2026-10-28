# API Endpoints

Base URL: `{API_BASE_URL}/v1`. JSON unless noted. All timestamps ISO 8601 UTC. All IDs are UUIDs.

## Conventions

**Auth** (one of):
- `Authorization: Bearer <JWT>` (dashboard, OIDC)
- `X-API-Key: ak_live_...` (CI, scoped)

**Common headers:** `X-Request-Id` (optional in, always out). `Content-Type: application/json`.

**Pagination:** `?limit=25&cursor=<opaque>`; response `{ "items": [...], "next_cursor": "..." | null }`.

**Errors:** `{ "error": { "code", "message", "details", "request_id" } }`. Status mapping: 400/422 `VALIDATION_ERROR`, 401 `UNAUTHENTICATED`, 403 `FORBIDDEN`, 404 `NOT_FOUND`, 409 `AUDIT_NOT_READY`, 410 `AUDIT_PURGED`, 413 `PAYLOAD_TOO_LARGE`, 429 `RATE_LIMITED`, 500 `INTERNAL`.

**Disclaimer:** every audit/report/finding response includes `"disclaimer": "<standard text>"`.

**Rate limits:** returned via `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After` on 429.

---

## Health and Identity

### `GET /health`
No auth. `200 {"status":"ok","version":"x.y.z"}`

### `GET /me`
`200 {"user":{"id","email","role"},"org":{"id","name"},"limits":{"max_upload_mb","audits_per_hour"}}`

---

## API Keys

### `POST /api-keys`  (Bearer only)
Body: `{"name":"ci-main","scopes":["audits:write","audits:read"]}`
`201 {"id","name","key":"ak_live_...","key_prefix","scopes","created_at"}`  The full key is shown once.

### `GET /api-keys`
`200 {"items":[{"id","name","key_prefix","scopes","last_used_at","revoked_at","created_at"}]}`

### `DELETE /api-keys/{id}`
`204`

---

## Projects

### `POST /projects`
Body: `{"name":"MyVault","description":"optional"}` → `201 Project`

### `GET /projects`  → `200 {items:[Project], next_cursor}`
### `GET /projects/{project_id}`  → `200 Project`
### `DELETE /projects/{project_id}`  → `204` (soft delete; purges audits)

`Project`: `{id, name, description, created_at, audit_count, latest_audit: {id,status,created_at}|null}`

---

## Uploads

### `POST /uploads`  (multipart/form-data)
Field `file`: `.sol` or `.zip`. Limits: `MAX_UPLOAD_MB`.
`201 {"upload_id","kind":"sol|zip","size_bytes","sha256","expires_at"}`
Errors: `413`, `422 UNSUPPORTED_SOURCE`.

---

## Audits

### `POST /projects/{project_id}/audits`
Body:
```json
{
  "upload_id": "uuid",
  "options": {
    "solc_version": "0.8.24",
    "features": ["privilege_map","findings","rag","patches"],
    "include_dependencies": false,
    "retention_hours": 24
  },
  "role_declarations": [
    {"role_key":"OWNER","holder_type":"multisig","threshold":3,"signers":5}
  ]
}
```
`202 {"audit_id","status":"queued","events_url":"/v1/audits/{id}/events"}`
Allowed `features`: `privilege_map` (default on), `findings`, `rag`, `patches`, `proofs`, `invariants` (later milestones are rejected with `422` until enabled).

### `GET /audits?project_id=&status=&limit=&cursor=`
`200 {items:[AuditSummary], next_cursor}`

### `GET /audits/{audit_id}`
`200 Audit`:
```json
{
  "id":"", "project_id":"", "status":"queued|running|complete|failed|cancelled",
  "stage":"privilege_map", "options":{}, "compiler_version":"0.8.24",
  "toolchain":{"solc":"","slither":"","foundry":""}, "corpus_version":"2026.10.1",
  "coverage":{"analyzed":{},"not_analyzed":[],"out_of_scope":[]},
  "scores":{"overall":72,"security":72,"label":"heuristic risk indicator"},
  "counts":{"critical":0,"high":2,"medium":3,"low":1,"info":4},
  "error":null, "created_at":"", "finished_at":null, "purge_after":"",
  "disclaimer":""
}
```
`410` if purged.

### `GET /audits/{audit_id}/events`  (Server-Sent Events)
`Content-Type: text/event-stream`. Supports `Last-Event-ID` for resume.
Event types: `stage_started`, `stage_completed`, `log`, `finding_added`, `privilege_map_ready`, `patch_ready`, `audit_completed`, `audit_failed`.
```
id: 142
event: stage_completed
data: {"stage":"analyzing","duration_ms":3120}
```
Stream ends after a terminal event. Heartbeat comment every 15 s.

### `POST /audits/{audit_id}/cancel`  → `202 {"status":"cancelling"}`
### `DELETE /audits/{audit_id}`  → `204` (immediate purge of artifacts and source-derived data)

### `GET /audits/{audit_id}/files`
`200 {items:[{id,path,sha256,line_count,is_dependency}]}`

### `GET /audits/{audit_id}/files/{file_id}`
`200 {"id","path","language":"solidity","content":"..."}` (`409` if not ready, `410` if purged)

---

## Privilege Map

### `GET /audits/{audit_id}/privilege-map`
`200 PrivilegeMap`:
```json
{
  "roles":[{
    "role_key":"OWNER","display_name":"Owner","blast_score":95,"tier":"critical",
    "worst_case":"Owner can mint unbounded tokens to any address with no delay. No timelock, no cap, no multisig assumed.",
    "holder_assumed":true,
    "declaration":null,
    "can_grant":["MINTER_ROLE"],
    "actions":[{
      "id":"","contract":"Token","function_signature":"mint(address,uint256)",
      "span":{"file":"src/Token.sol","start_line":42,"end_line":47,"sha256":""},
      "power_category":"MINT","guard_kind":"modifier","guard_roles":["OWNER"],
      "mitigations":{"cap":null,"delay_seconds":0,"two_step":false,"reversible":false},
      "funds_impact":3,"score":85
    }],
    "breakdown":[{"action_id":"","base":85,"cap_mult":1.0,"delay_mult":1.0,"reversible_mult":1.0,"holder_mult":1.0,"score":85}]
  }],
  "edges":[{"from":"OWNER","to":"MINT:Token.mint","kind":"can_call"},
           {"from":"OWNER","to":"MINTER_ROLE","kind":"can_grant"}],
  "undetected_notes":["Assembly block at src/Token.sol:88 not analyzed"],
  "scoring_config_version":"1",
  "disclaimer":""
}
```
`409 AUDIT_NOT_READY` until stage `privilege_map` completes.

### `PUT /audits/{audit_id}/role-declarations`
Body:
```json
{"declarations":[
  {"role_key":"OWNER","holder_type":"timelock_multisig","threshold":3,"signers":5,"delay_hours":48}
]}
```
Replaces the full declaration set. Synchronous recompute. `200 PrivilegeMap` (same shape as above).
Validation: `threshold<=signers`, `delay_hours>=0`, `role_key` must exist in the map.

### `GET /audits/{audit_id}/role-declarations`  → `200 {declarations:[...]}`

---

## Findings

### `GET /audits/{audit_id}/findings?severity=&source=&status=&scored=&limit=&cursor=`
`200 {items:[FindingSummary], next_cursor}`
`FindingSummary`: `{id,title,severity,confidence,source,status,scored,file,start_line,end_line,has_patch,proven}`

### `GET /audits/{audit_id}/findings/{finding_id}`
```json
{
  "id":"","title":"","severity":"high","confidence":0.82,"source":"slither","scored":true,
  "spans":[{"file":"","start_line":0,"end_line":0,"sha256":""}],
  "description":"","scenario":"",
  "evidence":[
    {"kind":"static_fact","title":"Slither: reentrancy-eth","locator":"src/Vault.sol:57","facts":{}},
    {"kind":"swc","title":"SWC-107 Reentrancy","locator":"SWC-107","source_url":"https://...",
     "quote":"...exact substring...","retrieval_score":0.71}
  ],
  "patch":{"id":"","status":"verified"} ,
  "proof":null,
  "status":"open","disclaimer":""
}
```

### `PATCH /audits/{audit_id}/findings/{finding_id}`
Body: `{"status":"dismissed","reason":"false positive"}` → `200 Finding`. Allowed: `open`, `dismissed`.

### `GET /audits/{audit_id}/observations`
Unscored `llm_hypothesis` list, same shape as findings, clearly labeled `scored:false`.

---

## Patches (Milestone 5)

### `POST /audits/{audit_id}/findings/{finding_id}/patches`
Body: `{}` (generate) → `202 {"patch_id","status":"draft"}` (progress over SSE `patch_ready`).
### `GET /audits/{audit_id}/findings/{finding_id}/patches`  → `200 {items:[Patch]}`
### `GET /patches/{patch_id}`
```json
{"id":"","finding_id":"","version":1,"status":"verified",
 "unified_diff":"--- a/src/Vault.sol\n+++ b/src/Vault.sol\n@@ ...",
 "rationale":"","compiles":true,"finding_cleared":true,"new_findings":[],
 "tests_passed":null,"gas_delta":{"withdraw(uint256)":-120},
 "verification_log":[{"step":"compile","ok":true}],"disclaimer":""}
```
### `POST /patches/{patch_id}/verify`
Body: `{"unified_diff":"<user-edited diff>"}` → `202 {"patch_id","version":2,"status":"draft"}`; result via SSE and `GET`.

---

## Proofs (Milestone 6)

### `POST /audits/{audit_id}/findings/{finding_id}/proof`  → `202 {"proof_id"}`
### `GET /findings/{finding_id}/proof`
`200 {"id","test_source","fails_on_original":true,"passes_on_patched":true,"run_log":[...]}` or `404`.

---

## Invariants (Milestone 7)

### `POST /audits/{audit_id}/invariant-runs`
Body: `{"contract_id":"uuid","contract_type_override":"erc4626"|null,"templates":["all"]}` → `202 {"run_group_id"}`
### `GET /audits/{audit_id}/invariant-runs`
`200 {items:[{id,contract,template_id,description,status,counterexample|null}]}`

---

## Export

### `GET /audits/{audit_id}/export?format=json|md|sarif|pdf`
`200` with `Content-Disposition: attachment`. `409` if not complete. Every format includes the disclaimer, coverage, toolchain, corpus version, scoring weights.

---

## Corpus (read-only)

### `GET /corpus/versions`
`200 {"current":"2026.10.1","documents":{"swc":37,"postmortem":104}}`

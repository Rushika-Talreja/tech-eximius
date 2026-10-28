# Milestone M0 Architecture & Implementation Notes

This document details the foundation implementation for Milestone M0 of the **DeFi Contract Auditor**, covering design decisions, specifications, test matrices, and operational instructions.

---

## 1. M0 Status Matrix

| Component | Status | Primary Location | Verification Method |
| :--- | :--- | :--- | :--- |
| **Monorepo Structure** | DONE | `packages/`, `services/`, `apps/`, `infra/` | Directory tree inspection per AGENTS.md |
| **Makefile Targets** | DONE | `Makefile` | `make setup`, `make test`, `make api`, etc. |
| **Pre-commit Suite** | DONE | `.pre-commit-config.yaml`, `.secrets.baseline` | `make lint`, `make precommit` |
| **Docker Compose Services** | DONE | `infra/docker-compose.yml` | Postgres 16, Redis, Qdrant, MinIO init |
| **Database Models & RLS** | DONE | `services/api/app/db/models.py`, `alembic/` | Multi-dialect (PG RLS & SQLite local dev) |
| **Alembic Initial Migration** | DONE | `services/api/alembic/versions/0001_initial_schema.py` | `alembic upgrade head` |
| **OIDC JWT Auth & Provisioning** | DONE | `services/api/app/auth.py` | Same validation path; autoprovisions user & org |
| **Local JWT Minting Helper** | DONE | `services/api/app/devtools/mint_token.py` | `make token-a`, `make token-b`, `python -m app.devtools.mint_token` |
| **API Keys Management & Scoping**| DONE | `services/api/app/routers/api_keys.py`, `auth.py` | HMAC-SHA256, prefix, scoped (`audits:write`/`read`) |
| **Tenant Isolation** | DONE | `services/api/app/auth.py`, `routers/projects.py` | `app.org_id` scoped queries and Postgres RLS |
| **Projects CRUD** | DONE | `services/api/app/routers/projects.py` | Full project lifecycle endpoints |
| **Log Scrubber** | DONE | `services/api/app/logging_config.py` | Structlog recursive scrubber dropping sensitive fields |
| **Standard Error Envelope** | DONE | `services/api/app/errors.py`, `main.py` | `{ "error": { "code", "message", "details", "request_id" } }` |
| **Rate Limiter (429 Envelope)** | DONE | `services/api/app/rate_limiter.py` | Sliding window per-principal with `Retry-After` header |
| **Worker Skeleton & SSE** | DONE | `services/worker/`, `services/api/app/routers/audits.py` | SSE `/audits/{id}/events` with Last-Event-ID & heartbeat |
| **OpenAPI & Type Generation** | DONE | `openapi.json`, `Makefile` | `make gen-types`, `make gen-console-types` |
| **Stub Interfaces (Core)** | STUBBED| `packages/auditor_core/auditor_core/interfaces.py` | `retrieve_evidence()`, `verify_draft()` with TODO(spec) |
| **M1 Uploads & Safety Checks**| DONE | `services/api/app/routers/uploads.py` | Zip safety (traversal, symlinks, bombs, size) |
| **M1 Analysis Sandbox Runner**| DONE | `packages/auditor_core/auditor_core/sandbox/runner.py` | Network isolation, non-root, timeout, secret scrubbing |
| **M1 Building Stage Pipeline**| DONE | `packages/auditor_core/auditor_core/pipeline/building.py` | Layout detection, solc-select, mixed pragmas, diagnostics |
| **M1 Retention & Purge Job**  | DONE | `services/api/app/retention.py`, `routers/audits.py` | Immediate purge on DELETE, scheduled purge, 410 AUDIT_PURGED |
| **M2 Slither & Privilege Map** | NOT DONE| Out of scope for M1 | Deferred to Milestone M2 |

---

## 2. Key Design Decisions

### Auth & Token Minting
- **Production Path**: All tokens are validated via RS256/ES256 against JWKS via standard PyJWT/python-jose without custom bypass strings.
- **Local Dev Minting (`APP_ENV=local`)**:
  - `python -m app.devtools.mint_token --user a|b [--ttl 3600]` or `make token-a` / `make token-b`.
  - Refuses execution and exits non-zero if `APP_ENV != local`.
  - Generates a 2048-bit RSA keypair stored under `.local/dev_rsa_key.pem` (mode `0600`) and `.local/dev_jwks.json`.
  - When `APP_ENV=local`, `auth.py` loads the public JWKS directly into the JWKS verification cache, guaranteeing the exact same validation pipeline runs in local development as in production.

### Multi-Dialect Tenant Isolation & Database Support
- Production and staging use PostgreSQL 16 with Row-Level Security (RLS) policies enforcing `org_id = NULLIF(current_setting('app.org_id', true), '')::uuid`.
- To support local zero-docker development and lightweight test environments, SQLAlchemy models use multi-dialect primitives (`UniversalUUID`, `UniversalJSON`, `UniversalArray`), allowing fallback to SQLite (`aiosqlite`).
- `set_rls_org` executes `SET LOCAL app.org_id` on PostgreSQL while bypassing on SQLite, while application-level queries strictly enforce `Project.org_id == principal.org_id`.

### API Key Security & Hashing
- API keys are prefixed with `ak_live_` and generated with 32+ bytes of cryptographically secure random entropy.
- Raw keys are shown to users once at creation time and never stored in the database.
- Stored representations contain only `key_prefix` (for fast index lookup) and `key_hash = HMAC-SHA256(pepper, raw_key)`.
- Scopes are enforced per route (`RequireWrite = require_scope("audits:write")`).
- `last_used_at` updates upon successful authentication. Revoked keys immediately return 401.

### Log Scrubbing & Customer Code Protection (AGENTS.md #6)
- Structlog processor recursively scrubs any key named `source`, `code`, `diff`, `prompt`, or `completion` from all log events.
- SQLAlchemy engine uses `echo=False` and `hide_parameters=True` to guarantee query parameters never leak into logs.
- Validation error handlers strip raw `input` objects from Pydantic 422 responses to ensure contract code is never echoed in error bodies.

### Error Envelope & Rate Limiting
- Every error follows the standard envelope: `{ "error": { "code", "message", "details", "request_id" } }`.
- Response header `X-Request-Id` is guaranteed to match `error.request_id`.
- In-memory sliding window limiter enforces rate limits per principal (or client IP), returning 429 with `Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining` headers.

---

## 3. `TODO(spec)` Ledger

| File | Line | Question / Detail for Spec Owner |
| :--- | :--- | :--- |
| `packages/auditor_core/auditor_core/interfaces.py` | 86 | `retrieve_evidence(candidate: CandidateSummary)`: Retrieval logic and Qdrant similarity thresholding owned by evidence workstream. Stub returns `RetrievalResult(evidence=[], degraded=False, corpus_version=None)`. |
| `packages/auditor_core/auditor_core/interfaces.py` | 99 | `verify_draft(...)`: Grounding verifier and semantic citation verification owned by evidence workstream. Stub returns draft unchanged. |
| `services/api/app/routers/uploads.py` | 30 | Zip compression ratio threshold for decompression bomb defense: spec does not give numeric threshold; currently set to safe default of 100:1. |
| `services/api/app/routers/exports.py` | 153 | PDF report rendering engine: library choice (WeasyPrint, ReportLab, or headless Chromium) needs architectural sign-off for container size and dependency requirements. |

---

## 4. Known Limitations & Risks

1. **SQLite vs. PostgreSQL RLS**: While SQLite allows local development without Docker, PostgreSQL RLS is only active when connected to PostgreSQL. All integration and staging deployments must test against Postgres 16.
2. **In-Memory Rate Limiter**: The sliding window rate limiter stores state in memory. In multi-replica deployments (staging/production), state must be backed by Redis (`redis_url`).
3. **Local RSA Key Storage**: The dev RSA keypair lives in `.local/` (git-ignored, mode `0600`). Deleting `.local/` rotates the dev key, invalidating previously minted local JWTs.

---

## 5. Exit Gates Checklist for Milestone M0

- [x] Monorepo structure conforms to AGENTS.md.
- [x] Pre-commit configuration with ruff, mypy, prettier, and detect-secrets baseline (`.pre-commit-config.yaml`).
- [x] Multi-tenant isolation verified with cross-tenant test (`test_cross_tenant.py`).
- [x] API key lifecycle, scoping, revocation, and hashing verified (`test_api_keys.py`).
- [x] Log scrubber and error body scrubbing verified (`test_log_scrub.py`).
- [x] Standard error envelope and 401, 403, 404, 422, 429 response verification (`test_error_format.py`).
- [x] Core stub interfaces exportable and verified (`test_interfaces.py`).
- [x] Local JWT minting helper functional and restricted to `APP_ENV=local` (`make token-a`, `make token-b`).
- [x] OpenAPI specification exported (`openapi.json`) and TypeScript types generated (`make gen-types`, `make gen-console-types`).

---

## 6. How to Run

### Standalone Local Mode (Zero Docker)
1. Initialize virtual environment and dependencies:
   ```bash
   make setup
   ```
2. Initialize local database:
   ```bash
   make migrate
   ```
3. Start the API server:
   ```bash
   make api
   ```
4. Start the local worker:
   ```bash
   make worker
   ```
5. Mint test tokens:
   ```bash
   make token-a
   make token-b
   ```
6. Run the test console:
   ```bash
   make console
   ```

### Docker Compose Mode
1. Start infrastructure services:
   ```bash
   docker compose -f infra/docker-compose.yml up -d
   ```
2. Run database migrations:
   ```bash
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/auditor alembic upgrade head
   ```
3. Run tests against PostgreSQL:
   ```bash
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/auditor make test
   ```

### Running Test Suite
```bash
make test
```
Runs all 29 unit and integration tests across `services/` and `packages/`.

---

## 7. Milestone M1: Uploads, Sandbox & Stage 1 Building Pipeline

### Upload Handling & Zip Safety
- `POST /v1/uploads`: Accepts `.sol` or `.zip` via multipart form upload.
- **Security Validations**:
  - Rejects unsupported extensions (`422 UNSUPPORTED_SOURCE`).
  - Enforces `max_upload_mb` cap (`413 PAYLOAD_TOO_LARGE`).
  - Inspects zip archives prior to extraction:
    - Path traversal (`../` or `..\\`) (`422 VALIDATION_ERROR`).
    - Absolute file paths (`422 VALIDATION_ERROR`).
    - Symlinks / directory traversal tricks (`422 VALIDATION_ERROR`).
    - Compression bomb / zip bomb ratio > 100:1 (`422 VALIDATION_ERROR`).
    - Total uncompressed size limit and file count limit.
- Encrypted object key layout: `{org_id}/uploads/{upload_id}`.

### Container & Sandbox Architecture
- **Dependency-Fetch Container (`services/sandbox/Dockerfile.fetch`)**:
  - Isolated container running as non-root (UID 10001).
  - Outbound network strictly restricted to package manager allowlist (`registry.npmjs.org`, GitHub).
  - Enforces `npm ci --ignore-scripts`, git submodule / forge install only.
  - User scripts, tasks, and postinstall hooks are never executed.
- **Analysis Sandbox Container (`services/sandbox/Dockerfile.analysis`)**:
  - Sealed execution with `--network none` (verified by `test_sandbox_network_request_fails`).
  - Read-only root filesystem with ephemeral `tmpfs` scratch space (`/tmp`, `/workspace/out`).
  - Non-root user (UID 10001:10001), restricted pids limit (128), memory limit (2GB), CPU limit (2.0).
  - Strips all secrets, database credentials, API peppers, and cloud keys from environment variables.
  - Enforces execution timeout (300s default) and caps compiler output size (10MB).

### Stage 1: Building Pipeline (`packages/auditor_core/.../pipeline/building.py`)
- **Layout Detection**:
  - `foundry.toml` -> Foundry layout.
  - `hardhat.config.js` / `.ts` -> Hardhat layout.
  - Loose `.sol` files -> auto-wrapped into standard compiler directory structure.
- **Compiler Version Selection**:
  - Discovers Solidity pragmas across source files.
  - Invokes `solc-select` to select matching binary.
  - Resolves mixed pragmas: compiles compatible files under highest compatible version; marks remaining incompatible files in `coverage.not_analyzed` with reasons.
- **Compilation & Error Handling**:
  - Compiles via `solc` standard JSON input.
  - Captures diagnostics with strictly structured schema (`file`, `line`, `column`, `message`).
  - On compilation failure: marks audit `status="failed"`, emits `audit_failed` event with `BUILD_FAILED` code.
  - **Hard Rule**: Never falls back to unverified LLM review when compilation fails.
- **Manifest & Persistence**:
  - Computes SHA256 hashes, line counts, and relative paths.
  - Stores deduplicated source artifacts to object storage at `{org_id}/audits/{id}/sources/{sha256}`.
  - Populates `audit_files` rows and updates `audit.source_manifest`, `audit.coverage`, and `audit.toolchain`.

### Retention & Immediate Purge
- Every audit carries a `purge_after` timestamp calculated from retention settings.
- `DELETE /v1/audits/{id}` executes immediate purge:
  - Deletes all storage objects under prefix `{org_id}/audits/{id}/`.
  - Deletes all source-derived `AuditFile` records from the database.
  - Verifies database record deletion before marking `purged_at`.
  - Scrubs `source_manifest` and `coverage` from the audit record.
  - Subsequent `GET /v1/audits/{id}` and `GET /v1/audits/{id}/files` immediately return `410 AUDIT_PURGED`.
- `purge_expired_audits()` periodically evaluates `Audit.purge_after <= now()` and executes the purge pipeline.

### M1 Exit Gates Checklist
- [x] `POST /v1/uploads` with comprehensive zip bomb, traversal, symlink, and size guards (`test_uploads.py`).
- [x] Network isolation verified inside sandbox (`test_sandbox.py`).
- [x] Compilation success and `BUILD_FAILED` diagnostics verified (`test_building_pipeline.py`).
- [x] Mixed pragma partitioning into `coverage.not_analyzed` verified (`test_building_pipeline.py`).
- [x] Immediate purge (`DELETE /v1/audits/{id}`) and retention expiration verified (`test_retention_and_delete.py`).
- [x] End-to-end deliverable verified: upload `vault_basic`, run audit, stream SSE events, fetch file, delete audit (`test_deliverable_e2e.py`).



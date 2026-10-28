# Backend Architecture

## 1. Components

```
Next.js ──REST/SSE──▶ FastAPI (services/api)
                         │  validates auth, writes DB, enqueues jobs
                         ▼
                  Postgres  ◀───────────────┐
                  Redis (Arq queue)         │
                         │                  │
                         ▼                  │
                 Worker (services/worker) ──┘  runs pipeline stages
                   │        │        │
                   ▼        ▼        ▼
            Sandbox      Qdrant     LLM provider
          (docker/gVisor) (security  (structured
           compile/analyze corpus)    output only)
                   │
                   ▼
            S3/MinIO (encrypted artifacts: sources, reports)
```

- **API** is thin: auth, validation, CRUD, job creation, SSE streaming from `audit_events`.
- **Worker** owns all heavy work. Each audit is a job executing ordered stages; stages are idempotent and checkpointed by writing results to Postgres.
- **Sandbox runner** is invoked by the worker through the Docker API (or `runsc`). No user code ever runs in the API or worker process.
- **Qdrant** holds only public corpus data (never customer code).

## 2. Process Model and Job State Machine

`audits.status`: `queued → running → complete | failed | cancelled`
`audits.stage` (while running): `building → analyzing → privilege_map → scanning → retrieving → synthesizing → [patching → verifying] → reporting`

Rules:
- Each stage writes `audit_events` rows (`stage`, `level`, `message`, optional `data`) consumed by SSE.
- A stage failure sets `status=failed` with a structured `error` (`code`, `message`, `stage`). Build failures return code `BUILD_FAILED` with compiler diagnostics (no source echoed beyond file:line:col and message).
- Cancel: API sets `cancel_requested`; the worker checks between stages and kills the sandbox container.
- Retention: `purge_after = created_at + retention`; a scheduled purge job deletes object-store artifacts and source-derived rows content, sets `purged_at`. User delete triggers immediate purge.

## 3. Database Schema (PostgreSQL)

All tenant tables carry `org_id` and have RLS: `USING (org_id = current_setting('app.org_id')::uuid)`. The API sets `app.org_id` per request/transaction.

```sql
create table organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table users (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id),
  idp_subject text not null unique,
  email text not null,
  role text not null check (role in ('owner','member')) default 'member',
  created_at timestamptz not null default now()
);

create table api_keys (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id),
  user_id uuid not null references users(id),
  name text not null,
  key_prefix text not null,            -- first 8 chars, shown in UI
  key_hash text not null,              -- HMAC-SHA256(pepper, key)
  scopes text[] not null default '{audits:write,audits:read}',
  last_used_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create table projects (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id),
  name text not null,
  description text,
  created_by uuid not null references users(id),
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table uploads (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id),
  user_id uuid not null references users(id),
  object_key text not null,
  kind text not null check (kind in ('sol','zip')),
  size_bytes bigint not null,
  sha256 text not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table audits (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id),
  project_id uuid not null references projects(id),
  created_by uuid not null references users(id),
  status text not null check (status in ('queued','running','complete','failed','cancelled')),
  stage text,
  options jsonb not null default '{}',     -- features, solc_version override, etc.
  compiler_version text,
  toolchain jsonb,                         -- slither/foundry/solc versions
  corpus_version text,
  source_manifest jsonb,                   -- [{path, sha256, lines}]
  coverage jsonb,                          -- analyzed / not analyzed statement
  error jsonb,
  cancel_requested boolean not null default false,
  started_at timestamptz,
  finished_at timestamptz,
  purge_after timestamptz not null,
  purged_at timestamptz,
  created_at timestamptz not null default now()
);

create table audit_files (
  id uuid primary key default gen_random_uuid(),
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  path text not null,
  sha256 text not null,
  line_count int not null,
  object_key text not null,
  is_dependency boolean not null default false,
  unique (audit_id, path)
);

create table contracts (
  id uuid primary key default gen_random_uuid(),
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  file_id uuid not null references audit_files(id),
  name text not null,
  kind text not null check (kind in ('contract','library','interface','abstract')),
  start_line int not null, end_line int not null,
  contract_type text,                      -- erc20|erc4626|staking|lending|other
  upgradeability text,                     -- none|transparent|uups|beacon|diamond|unknown
  semantic jsonb not null                  -- ContractSemanticModel
);

create table role_declarations (
  id uuid primary key default gen_random_uuid(),
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  role_key text not null,
  holder_type text not null check (holder_type in
    ('eoa','multisig','timelock_multisig','contract_unknown','renounced')),
  params jsonb not null default '{}',      -- {threshold, signers, delay_hours}
  updated_at timestamptz not null default now(),
  unique (audit_id, role_key)
);

create table role_nodes (
  id uuid primary key default gen_random_uuid(),
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  role_key text not null,                  -- OWNER | DEFAULT_ADMIN_ROLE | MINTER_ROLE | CUSTOM:<modifier>
  display_name text not null,
  kind text not null check (kind in ('owner','access_control','custom','proxy_admin')),
  admin_role_key text,                     -- who can grant/revoke this role
  unique (audit_id, role_key)
);

create table privileged_actions (
  id uuid primary key default gen_random_uuid(),
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  contract_id uuid not null references contracts(id),
  file_id uuid not null references audit_files(id),
  function_signature text not null,
  start_line int not null, end_line int not null,
  power_category text not null,            -- see taxonomy in features.md
  guard_kind text not null,                -- modifier|require_sender|role_check|none
  guard_roles text[] not null default '{}',
  mitigations jsonb not null default '{}', -- {cap:{...}, delay:{seconds}, two_step:bool, reversible:bool}
  funds_impact smallint not null,          -- 0..3
  facts jsonb not null                     -- raw deterministic facts for evidence
);

create table privilege_results (
  id uuid primary key default gen_random_uuid(),
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  role_key text not null,
  blast_score smallint not null check (blast_score between 0 and 100),
  tier text not null check (tier in ('none','low','medium','high','critical')),
  worst_case text not null,
  holder_assumed boolean not null,
  breakdown jsonb not null,                -- per-action score components
  computed_at timestamptz not null default now(),
  unique (audit_id, role_key)
);

create table findings (
  id uuid primary key default gen_random_uuid(),
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  source text not null check (source in
    ('slither','privilege_map','custom_detector','invariant','exploit_proof','llm_hypothesis')),
  detector text,
  category text not null check (category in ('security')),   -- 'compliance' reserved for later
  title text not null,
  severity text not null check (severity in ('critical','high','medium','low','info')),
  confidence numeric(3,2) not null check (confidence between 0 and 1),
  file_id uuid references audit_files(id),
  start_line int, end_line int,
  description text not null,
  scenario text,
  status text not null default 'open' check (status in ('open','dismissed','patched')),
  scored boolean not null default true,    -- false for llm_hypothesis
  created_at timestamptz not null default now()
);

create table finding_evidence (
  id uuid primary key default gen_random_uuid(),
  finding_id uuid not null references findings(id) on delete cascade,
  org_id uuid not null,
  kind text not null check (kind in ('static_fact','swc','postmortem','proof')),
  chunk_id text,                           -- Qdrant point/chunk id for swc/postmortem
  title text not null,
  source_url text,
  locator text,                            -- SWC-107, incident id, or file:line
  quote text,                              -- exact substring of stored chunk
  retrieval_score real,
  facts jsonb                              -- for static_fact: detector output
);
-- Enforced in service layer + deferred constraint trigger: every finding has >= 1 evidence row.

create table patches (
  id uuid primary key default gen_random_uuid(),
  finding_id uuid not null references findings(id) on delete cascade,
  org_id uuid not null,
  version int not null default 1,
  unified_diff text not null,
  rationale text not null,
  compiles boolean, finding_cleared boolean, new_findings jsonb,
  tests_passed boolean, gas_delta jsonb,
  verification_log jsonb,
  status text not null default 'draft' check (status in ('draft','verified','failed','rejected','applied')),
  created_at timestamptz not null default now()
);

create table proofs (                      -- Milestone 6
  id uuid primary key default gen_random_uuid(),
  finding_id uuid not null references findings(id) on delete cascade,
  org_id uuid not null,
  test_source text not null,
  fails_on_original boolean, passes_on_patched boolean,
  run_log jsonb, created_at timestamptz not null default now()
);

create table invariant_runs (              -- Milestone 7
  id uuid primary key default gen_random_uuid(),
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  contract_id uuid not null references contracts(id),
  template_id text not null,
  status text not null check (status in ('passed','violated','error','skipped')),
  counterexample jsonb,                    -- call sequence + state
  run_log jsonb,
  created_at timestamptz not null default now()
);

create table audit_events (
  id bigserial primary key,
  audit_id uuid not null references audits(id) on delete cascade,
  org_id uuid not null,
  ts timestamptz not null default now(),
  stage text, level text not null default 'info',
  message text not null, data jsonb
);
create index on audit_events (audit_id, id);

create table corpus_documents (            -- metadata mirror of Qdrant corpus
  id text primary key,                     -- doc_id
  kind text not null check (kind in ('swc','postmortem')),
  title text not null, source_url text, license text,
  content_hash text not null, version text not null,
  created_at timestamptz not null default now()
);
```

Indexes: `(org_id, created_at)` on audits and projects; `(audit_id)` on all child tables; `(finding_id)` on evidence/patches/proofs.

## 4. Core Data Models (Pydantic, in `/packages/schemas`)

```python
class CodeSpan(BaseModel):
    file: str; start_line: int; end_line: int; sha256: str

class Evidence(BaseModel):
    kind: Literal["static_fact", "swc", "postmortem", "proof"]
    title: str
    locator: str | None = None
    source_url: HttpUrl | None = None
    chunk_id: str | None = None
    quote: str | None = Field(default=None, max_length=500)
    retrieval_score: float | None = None
    facts: dict | None = None

class Finding(BaseModel):
    id: UUID
    source: Literal["slither","privilege_map","custom_detector","invariant","exploit_proof","llm_hypothesis"]
    title: str
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    spans: list[CodeSpan]
    description: str
    scenario: str | None
    evidence: list[Evidence] = Field(min_length=1)   # HARD GUARDRAIL
    scored: bool = True
    patch_id: UUID | None = None

class PrivilegedAction(BaseModel):
    contract: str; function_signature: str; span: CodeSpan
    power_category: PowerCategory
    guard_kind: Literal["modifier","require_sender","role_check","none"]
    guard_roles: list[str]
    mitigations: Mitigations           # cap, delay_seconds, two_step, reversible
    funds_impact: int = Field(ge=0, le=3)
    facts: dict

class RoleHolderDeclaration(BaseModel):
    role_key: str
    holder_type: Literal["eoa","multisig","timelock_multisig","contract_unknown","renounced"]
    threshold: int | None = None; signers: int | None = None
    delay_hours: float | None = None

class RoleRisk(BaseModel):
    role_key: str; display_name: str
    blast_score: int; tier: Tier
    worst_case: str; holder_assumed: bool
    actions: list[PrivilegedAction]
    can_grant: list[str]
    breakdown: list[ScoreComponent]

class PrivilegeMap(BaseModel):
    roles: list[RoleRisk]
    edges: list[Edge]                   # role -> power, role -> role (grant)
    undetected_notes: list[str]         # honest blind spots

class AuditReport(BaseModel):
    audit_id: UUID; status: str
    coverage: CoverageStatement
    privilege_map: PrivilegeMap | None
    findings: list[Finding]
    patches: list[PatchSummary]
    toolchain: dict; corpus_version: str | None
    disclaimer: str                     # always populated
```

`CoverageStatement`: `analyzed` (files, contracts, detectors run), `not_analyzed` (reasons: unresolved imports, assembly blocks, proxies without implementation, off-chain config unknown), `out_of_scope` (fixed list: economic design, oracle trust, governance, off-chain components, deployment config).

## 5. Object Storage Layout

```
s3://auditor-artifacts/{org_id}/uploads/{upload_id}
s3://auditor-artifacts/{org_id}/audits/{audit_id}/sources/{sha256}
s3://auditor-artifacts/{org_id}/audits/{audit_id}/reports/report.json|sarif|md|pdf
```
Server-side encryption with per-tenant keys (KMS in staging/prod). Signed URLs for download only, short TTL.

## 6. Qdrant (MVP: one collection)

`security_postmortems`: named vectors `dense` (size = `EMBEDDING_DIM`, cosine) and sparse `bm25`. Payload: `doc_id, chunk_id, level (taxonomy|incident|chunk), vuln_class[], swc_ids[], cwe_ids[], incident_name, date, loss_usd, source_url, source_type, license, content_hash, text`. Payload indexes on `vuln_class`, `level`, `source_type`. A second collection `regulatory_clauses` is reserved for the deferred phase, do not create it yet.

## 7. Auth and Tenancy

- Dashboard: Bearer JWT from OIDC provider, validated via JWKS (issuer, audience, expiry). First login provisions `users` + `organizations` row.
- CI: `X-API-Key: ak_live_...` (hash lookup, scope check, rate limited).
- Dependency `get_principal()` returns `{org_id, user_id, scopes, auth_type}`; every DB session sets `app.org_id`.

## 8. Error Model

```json
{ "error": { "code": "BUILD_FAILED", "message": "...", "details": {}, "request_id": "..." } }
```
Codes: `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `RATE_LIMITED`, `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_SOURCE`, `BUILD_FAILED`, `AUDIT_NOT_READY`, `AUDIT_PURGED`, `OUT_OF_SCOPE`, `INTERNAL`.

## 9. Observability

Structured logs with `request_id`, `org_id`, `audit_id`, `stage`, `duration_ms`. A log filter drops any field named `source`, `code`, `diff`, `prompt`, or `completion`. Traces per stage. Metrics: stage duration, LLM tokens and cost per audit, verifier rejection rate, sandbox failures.

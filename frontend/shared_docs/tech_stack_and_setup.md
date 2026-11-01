# Tech Stack and Local Setup

Pin versions to the latest stable at project start and record them in lockfiles. Versions below are minimums/targets, not guarantees.

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind, shadcn/ui | Dark theme default |
| Code viewer / diff | Monaco editor, `react-diff-view` (or Monaco diff) | |
| Graph | `@xyflow/react` (React Flow) | Privilege Map |
| Server state | TanStack Query | |
| UI state | Zustand | Minimal |
| API client | `openapi-typescript` + thin fetch wrapper | Types generated from OpenAPI |
| Backend | Python 3.12, FastAPI, Pydantic v2, uvicorn | |
| ORM / migrations | SQLAlchemy 2.0 (async), Alembic | |
| Queue / workers | Redis + Arq | Async-native |
| DB | PostgreSQL 16 | RLS enabled |
| Object storage | S3-compatible (MinIO locally) | Encrypted artifacts |
| Vector DB | Qdrant | Dense + sparse hybrid |
| Embeddings | fastembed (dense + sparse BM25/SPLADE) | Model configurable |
| Code analysis | Tree-sitter (`tree-sitter-solidity`), Slither, `solc-select` | |
| Test/exploit runtime | Foundry (`forge`, `anvil`) | Milestone 6+ |
| LLM access | Provider-agnostic `LLMClient` interface | Structured output only |
| Auth | External OIDC provider (JWT/JWKS) | Provider configurable |
| Observability | OpenTelemetry, structlog, Sentry (redacted) | |
| Containers | Docker; gVisor (`runsc`) for prod sandboxes | |

## Environment Variables

```
# Core
APP_ENV=local|staging|prod
API_BASE_URL=http://localhost:8000
WEB_BASE_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000

# Database / queue / storage
DATABASE_URL=postgresql+asyncpg://auditor:auditor@localhost:5432/auditor
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET=auditor-artifacts
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
ARTIFACT_ENCRYPTION_KEY_ID=...        # KMS key id or local dev key
DEFAULT_RETENTION_HOURS=24

# Auth
OIDC_ISSUER_URL=...
OIDC_AUDIENCE=...
OIDC_JWKS_URL=...
API_KEY_HASH_PEPPER=...

# Vector DB / embeddings
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5   # re-evaluate on golden set
EMBEDDING_DIM=384
SPARSE_MODEL=Qdrant/bm25
RAG_MIN_SCORE=0.35                        # calibrate on eval set
RAG_TOP_K=20

# LLM
LLM_PROVIDER=...
LLM_API_KEY=...
LLM_MODEL_REASONING=...                   # patches, exploit tests
LLM_MODEL_FAST=...                        # query building, polishing
LLM_ZERO_RETENTION=true                   # must be true in staging/prod

# Sandbox
SANDBOX_RUNTIME=docker|runsc
SANDBOX_CPU_LIMIT=2
SANDBOX_MEM_LIMIT_MB=2048
SANDBOX_TIMEOUT_SECONDS=300
DEPENDENCY_FETCH_ALLOWLIST=registry.npmjs.org,github.com,codeload.github.com

# Limits
MAX_UPLOAD_MB=10
MAX_FILES_PER_AUDIT=200
AUDITS_PER_HOUR_PER_ORG=20
```

## docker-compose (local services)

Services: `postgres`, `redis`, `qdrant`, `minio` (+ bucket init). API, worker and web run on the host via `make` targets for hot reload. A `sandbox-build` image (solc-select, Slither, Foundry) is built from `/services/sandbox/Dockerfile.analysis`; a separate `sandbox-fetch` image handles dependency fetching.

## Sandbox Images

| Image | Network | Contents | Purpose |
|---|---|---|---|
| `sandbox-fetch` | Allowlist only, no secrets | git, node, npm (`--ignore-scripts`), forge install | Pre-fetch dependencies into a volume |
| `sandbox-analysis` | **none** | python, solc-select, Slither, tree-sitter, Foundry | Compile + analysis |
| `sandbox-test` (M6+) | **none** | Foundry | Run generated exploit/regression tests |

All run non-root, read-only root filesystem, tmpfs for scratch, CPU/mem/pids limits, seccomp default, destroyed after each job.

## First-Run Checklist

1. `make setup && make up && make migrate`
2. `python -m auditor.corpus ingest corpus/seed` (loads security corpus into Qdrant)
3. `make api`, `make worker`, `make web`
4. Upload `fixtures/contracts/vault_basic` through the UI and confirm the Privilege Map renders.

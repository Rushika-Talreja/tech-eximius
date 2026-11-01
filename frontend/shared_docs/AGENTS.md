# AGENTS.md: Instructions for AI Coding Agents

Read `README.md` first. Build milestones in `build_plan.md` order. Do not start a later milestone before the earlier one meets its Definition of Done.

## Repository Layout (monorepo)

```
/apps/web                  Next.js dashboard (TypeScript)
/services/api              FastAPI app (routes, auth, schemas, DB access)
/services/worker           Arq worker: pipeline stages
/services/sandbox          Dockerfiles + runner for compile/analysis/test containers
/packages/auditor_core     Python lib: analysis, privilege map, RAG, verifier, patching
/packages/schemas          Pydantic models (source of truth) + generated TS types
/corpus/seed               Hand-curated security corpus (YAML)
/corpus/ingest             Ingestion CLI
/eval                      Golden sets + eval harness
/fixtures/contracts        Test contracts with expected-output snapshots
/infra                     docker-compose, Terraform/Helm (later)
/docs                      These documents
```

## Commands (define these in a Makefile; keep them working)

```
make setup        # install python + node deps, pre-commit hooks
make up           # docker compose up (postgres, redis, qdrant, minio)
make migrate      # alembic upgrade head
make api          # run FastAPI with reload
make worker       # run Arq worker
make web          # run Next.js dev server
make test         # backend unit + integration tests
make test-web     # frontend tests
make lint         # ruff, mypy, eslint, prettier --check
make gen-types    # regenerate TS types from OpenAPI
make eval         # run eval harness (offline, mocked LLM unless EVAL_LIVE=1)
```

## Hard Rules

1. **Schemas first.** Pydantic models in `/packages/schemas` are the source of truth. Frontend types are generated from OpenAPI, never hand-written for API payloads.
2. **Evidence required.** A `Finding` cannot be persisted with zero evidence records. Enforce in the model validator AND a DB constraint/trigger check in the service layer.
3. **LLM never decides alone.** LLM output must be parsed into Pydantic models and passed through the verifier before persistence. No free-text LLM output is stored as a claim.
4. **No network in analysis sandboxes.** Compile/analysis/test containers run with `--network none`. Dependency fetching happens in a separate, allowlisted, no-secrets, no-script-execution step.
5. **Never execute user project scripts.** No `npm postinstall`, no Hardhat scripts, no `forge test` on user tests by default. Only our generated tests run (Milestone 6+).
6. **No customer code in logs, traces, error messages, or vector stores.** Log IDs, hashes, timings only.
7. **Pin everything.** Python, Node, solc, Slither, Foundry, and container image digests.
8. **Tenant isolation.** Every query is scoped by `org_id`. Add Postgres RLS policies; write a test that proves cross-tenant access fails.
9. **Disclaimers are mandatory** in API responses (`disclaimer` field), UI footer/banner, and all exports. Never use the words "certified", "safe", or "secure" as a verdict. Use "no verified issues detected by this analysis".
10. **Do not add scope.** No on-chain monitoring, wallet tracking, or compliance features until moved out of "Deferred".

## Code Conventions

- Python 3.12, type hints everywhere, `mypy --strict` on `packages/` and `services/`.
- Formatting: ruff (lint + format). Async FastAPI handlers, SQLAlchemy 2.0 async, Alembic migrations (never edit applied migrations).
- Errors: raise `AppError(code, message, status, details)`; the global handler formats the standard error body (see `api_endpoints.md`).
- Config via `pydantic-settings`; every env var documented in `tech_stack_and_setup.md`.
- TypeScript strict mode; no `any` without a comment; components are server components by default, client components only where interaction requires.
- Commit style: Conventional Commits. One milestone task per PR where possible.

## Definition of Done (per task)

- [ ] Code + types + migration (if any)
- [ ] Unit tests; integration test if it touches DB/queue/sandbox
- [ ] Fixture snapshot updated if analysis output changed (with human-reviewed diff)
- [ ] Docs updated if behavior or API changed (`api_endpoints.md`, `features.md`)
- [ ] `make lint test` pass
- [ ] No secrets, no customer code in logs (grep check in CI)

## When Unsure

Prefer the pessimistic, deterministic, evidence-backed behavior. If a spec is ambiguous, add a `TODO(spec):` comment, choose the safer option, and list the question in the PR description. Do not invent legal, regulatory, or security claims.

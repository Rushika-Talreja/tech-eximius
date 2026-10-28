# Build Plan

Execute milestones in order. Do not start a milestone until the previous one meets its Definition of Done (DoD). Time estimates assume a small team (1 to 3 engineers or agent-assisted) and are rough.

Legend: `[ ]` task, **DoD** = exit criteria, **Sec** = security checks required at the gate.

---

## M0: Foundations (about 1 week)

- [ ] Monorepo scaffolding per `AGENTS.md`; Makefile targets; pre-commit hooks
- [ ] `docker-compose` for postgres, redis, qdrant, minio; `make up`
- [ ] FastAPI skeleton: config, logging (with scrubbing filter), error model, `/health`
- [ ] Alembic setup + initial migration (orgs, users, api_keys, projects, uploads, audits, audit_events)
- [ ] OIDC JWT validation + user/org provisioning; API key auth
- [ ] Postgres RLS + `app.org_id` session setting + isolation test
- [ ] Arq worker skeleton with a no-op pipeline writing `audit_events`
- [ ] Next.js skeleton: auth, AppShell, theme tokens, DisclaimerBanner, Next proxy route
- [ ] OpenAPI export + `make gen-types`
- [ ] CI: lint, typecheck, unit tests, image build

**DoD:** log in, create a project, create a dummy audit, see SSE events from the no-op worker; RLS test passes.
**Sec:** secret scanning on; log-scrub test exists; CORS locked.

---

## M1: Ingest and Build (about 1 to 2 weeks)

- [ ] `POST /uploads` with zip safety (traversal, symlink, size, file-count, ratio checks)
- [ ] Layout detection (Foundry / Hardhat / loose)
- [ ] `sandbox-fetch` image + dependency fetch step (allowlist, `--ignore-scripts`)
- [ ] `sandbox-analysis` image (solc-select, Slither, Foundry) with pinned versions
- [ ] Sandbox runner (docker API) with limits from `security_and_guardrails.md`
- [ ] solc version selection from pragmas; compile via forge/solc; capture diagnostics
- [ ] Source manifest, `audit_files`, S3 storage, file listing/content endpoints
- [ ] `BUILD_FAILED` handling with diagnostics
- [ ] Frontend: New Audit page (upload, options), Overview with ProgressStepper, file tree + Monaco viewer
- [ ] Retention: `purge_after`, purge job, `DELETE /audits/{id}`

**DoD:** fixtures `vault_basic`, `mixed_pragmas`, `compile_error` behave as specified; zip bomb/traversal rejected; user can delete an audit and storage is verified empty.
**Sec:** sandbox egress test fails as expected; non-root and read-only rootfs verified; no source in logs.

---

## M2: Semantic Model and Privilege Map (about 2 to 3 weeks) **[flagship]**

- [ ] Tree-sitter spans + Slither IR extraction into `ContractSemanticModel`
- [ ] Contract type classification (erc20/erc4626/staking/lending/other)
- [ ] Role resolution (Ownable, AccessControl, custom modifiers, proxy admin)
- [ ] Power-category matchers (one function each, unit-tested)
- [ ] Mitigation detectors (cap, delay, two-step, reversible)
- [ ] Role graph with role-admin edges
- [ ] Scoring engine from `scoring_config.yaml`; worst-case templates
- [ ] `undetected_notes` generation (assembly, unresolved externals, missing proxy implementation)
- [ ] `GET privilege-map`, `PUT/GET role-declarations` (sync recompute)
- [ ] Fixtures + expected snapshots: `vault_basic`, `token_accesscontrol`, `custom_modifiers`, `timelocked_admin`, `capped_mint`, `uups_proxy`, `renounced_owner`, `inherited_guards`, `assembly_edge`
- [ ] Frontend: PrivilegeGraph (React Flow), RoleDrawer, HolderDeclarationForm, ScoreBreakdown, table view, filters, "What this view cannot see"
- [ ] Playwright E2E for Privilege Map including declaration change

**DoD:** all privilege fixtures match snapshots; eval accuracy targets met on the labeled set; declaration change recomputes under 300 ms; UI shows `Assumed` badge until declared; determinism test passes.
**Sec:** privilege results contain no raw source beyond spans/signatures.

---

## M3: Static Findings and Baseline Report (about 1 to 2 weeks)

- [ ] `detector_map.yaml`; Slither detector execution; custom detectors (unprotected privileged write, unbounded mint, unchecked upgrade auth)
- [ ] Candidate to Finding conversion with `static_fact` evidence; dedup
- [ ] Privilege-derived findings (high/critical unmitigated)
- [ ] Dependency/mocks exclusion with toggle
- [ ] Scoring (heuristic) + `CoverageStatement`
- [ ] Findings list/detail endpoints; dismiss action
- [ ] Reports: JSON, Markdown, SARIF; disclaimer in all
- [ ] Frontend: Findings list, detail with code highlight, Overview summary, Report page

**DoD:** `reentrancy_classic`, `unguarded_admin` produce expected findings; every finding has evidence (DB enforced); coverage card present; exports validated against schema/SARIF spec.

---

## M4: Security RAG and Grounding Verifier (about 2 weeks)

- [ ] Corpus seed format; ingestion CLI; Qdrant collection (dense + sparse)
- [ ] Curate seed corpus: SWC entries + about 100 incidents (own summaries, license recorded)
- [ ] Query builder (code-free input) with `LLMClient` abstraction
- [ ] Hybrid retrieval with vuln-class filter, threshold, parent-child expansion
- [ ] Synthesizer prompts (versioned) and structured outputs
- [ ] Grounding verifier (all checks in `analysis_pipeline.md`)
- [ ] `llm_hypothesis` observations list (unscored)
- [ ] Evidence UI (EvidenceCard, drawer, "no precedent retrieved" state)
- [ ] Eval: retrieval golden set (100+ pairs), unsupported-claim audit sample
- [ ] LLM provider zero-retention enforcement at startup

**DoD:** recall@5 at least 0.85; unsupported-claim rate under 1% on audit sample; injection fixture neutralized; Qdrant outage degrades gracefully with coverage note.
**Sec:** prompts/completions never logged; confirmed no customer code in Qdrant.

---

## M5: Patch Generator and Verifier (about 2 to 3 weeks)

- [ ] Patch planner prompt + structured output; diff rendering in code
- [ ] Verification loop: apply, compile, re-scan, finding-cleared check, new-findings check, storage-layout check for upgradeables
- [ ] Gas measurement via `forge snapshot` when tests exist
- [ ] 3-attempt retry with failure feedback; guidance-only fallback
- [ ] Endpoints: generate, list, get, verify (edited diff)
- [ ] Frontend: DiffViewer, status badges, Edit and re-verify, copy/download
- [ ] Optional: cross-encoder rerank in retrieval
- [ ] Eval: patch success rate on fixtures and benchmark

**DoD:** `reentrancy_classic` gets a verified patch; unverified patches are never offered; storage-layout change blocks patch on `uups_proxy`; patch success at least 70% on supported classes.
**Sec:** user project tests are **not** run; only our compile/analysis steps run in sandbox.

---

## M6: Prove-It Exploit Tests (about 2 to 3 weeks)

- [ ] `sandbox-test` image (Foundry, `ffi=false`, no network)
- [ ] Test-writer prompt for supported classes (reentrancy, access control, unchecked call, simple oracle read)
- [ ] Execution: must fail on original, pass on verified patch; flaky check (run twice)
- [ ] Assertion-quality check (test asserts attacker gain or invariant break)
- [ ] `proofs` storage, `proof` evidence, "Proven" badge, confidence uplift
- [ ] Frontend Proof tab (source view, run log)
- [ ] Rate limits and no-export-by-default

**DoD:** at least 80% of supported-class findings in fixtures produce valid proofs; no network or filesystem escape in test sandbox (tested).
**Sec:** misuse review sign-off.

---

## M7: Invariant Hunter Lite (about 2 to 3 weeks)

- [ ] Template format + metadata (`applies_if`); handler generation
- [ ] Templates: erc20, erc4626, staking, lending (human-written, reviewed)
- [ ] Contract-type confirmation/override UI
- [ ] Bounded `forge` invariant runs; counterexample extraction (minimal sequence)
- [ ] `invariant_runs` storage; invariant findings with `proof` evidence
- [ ] Fixtures: `erc4626_vulnerable`, `erc4626_clean`, others
- [ ] Frontend Invariants tab

**DoD:** vulnerable fixtures violated, clean fixtures pass; `skipped` always carries a reason; runs bounded in time.

---

## M8: Hardening and Beta (about 3 to 4 weeks)

- [ ] gVisor in staging/prod; load tests; cost per audit tracked
- [ ] PDF export; GitHub App/CI integration docs; API key UX polish
- [ ] Observability dashboards and alerts (verifier rejection spikes, sandbox failures)
- [ ] Red-team pass: injection, zip, sandbox egress, tenant isolation
- [ ] Terms of use, DPA/LLM subprocessor documentation, retention policy page
- [ ] Beta with design partners; collect auditor feedback on precision and Privilege Map accuracy

**DoD:** all eval gates green; security checklist signed; incident runbook rehearsed.

---

## Deferred Backlog (explicitly not scheduled)

1. Regulatory RAG (Collection B), jurisdiction toggle, compliance mechanics flags + counsel question lists
2. Security vs. compliance conflict resolver
3. LLM-inferred invariants with human confirm/edit (full Invariant Hunter)
4. Deployment-config input (constructor args, initial roles) for config-aware analysis
5. Multi-contract/system-level composability analysis
6. PR-diff-only audits and living risk history
7. Vyper and other EVM languages; L2-specific quirks
8. Self-hosted/BYOC deployment

## Dependency Graph (summary)

```
M0 → M1 → M2 → M3 → M4 → M5 → M6
              └──────────────→ M7 (needs M1 sandbox + M2 contract typing; can run parallel to M5/M6)
M3 → M8 (hardening after core flow works end to end)
```

## Risk Watchlist During Build

| Risk | Early signal | Response |
|---|---|---|
| Slither failures on real repos | High `BUILD_FAILED` / degraded analysis rate in beta | Improve build detection; Tree-sitter-only fallback; clear error UX |
| Privilege heuristics misclassify | Eval accuracy under target | Expand fixtures; prefer `OTHER_PRIVILEGED` over guessing; surface uncertainty in UI |
| RAG adds noise | Low recall@5 or irrelevant citations | Tighten class filters; raise threshold; show "no precedent" rather than weak matches |
| LLM cost/latency | Cost per audit over budget | Cache by content hash; slice code; use fast model tier; skip LLM stages gracefully |
| Users over-trust the score | Support tickets citing "audit passed" | Strengthen wording; coverage card above the score; remove score emphasis |

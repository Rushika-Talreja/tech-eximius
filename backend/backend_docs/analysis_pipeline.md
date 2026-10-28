# Analysis Pipeline

Implemented in `/packages/auditor_core`, orchestrated by `/services/worker`. Each stage is a function `async def run(ctx: AuditContext) -> None` that reads/writes Postgres and emits `audit_events`.

## Stage Overview

| # | Stage | Milestone | Network | LLM | Description |
|---|---|---|---|---|---|
| 1 | `building` | M1 | fetch step only | No | Resolve project, fetch deps, compile |
| 2 | `analyzing` | M2 | none | No | Tree-sitter + Slither semantic model |
| 3 | `privilege_map` | M2 | none | Wording only | Privileged actions, roles, scores |
| 4 | `scanning` | M3 | none | No | Slither detectors, custom detectors to candidate findings |
| 5 | `retrieving` | M4 | Qdrant | Query builder | Evidence retrieval per candidate |
| 6 | `synthesizing` | M4 | LLM | Yes | Draft finding text, run grounding verifier |
| 7 | `patching` | M5 | LLM | Yes | Draft patch plan, render diff |
| 8 | `verifying` | M5 | none | No | Compile, re-scan, gas diff on patched copy |
| 9 | `proving` | M6 | LLM | Yes | Exploit test generation and execution |
| 10 | `invariants` | M7 | none | No | Template invariant tests |
| 11 | `reporting` | M3+ | none | No | Score, coverage statement, exports |

## Stage 1: Building

1. Load upload; extract zip safely (reject path traversal, symlinks, files over size limit, more than `MAX_FILES_PER_AUDIT`).
2. Detect layout: Foundry (`foundry.toml`), Hardhat (`hardhat.config.*`), or loose `.sol` files.
3. **Fetch step** (separate container): install dependencies listed in `package.json` (`npm ci --ignore-scripts`), `forge install` for `.gitmodules`/`foundry.toml` libs, only from `DEPENDENCY_FETCH_ALLOWLIST`. Output to a read-only volume. No user scripts executed.
4. Pick solc version from pragmas (`solc-select`); if conflicting pragmas, compile each compatible group and note it in `coverage.not_analyzed`.
5. Compile in the no-network analysis container using `forge build` or `solc --standard-json` with remappings. Capture ASTs and diagnostics.
6. Build `source_manifest` (path, sha256, lines). Store files in S3, rows in `audit_files`.
7. On failure: `BUILD_FAILED` with diagnostics (file, line, column, message). Do **not** fall back to LLM-only review.

## Stage 2: Analyzing

Produces a `ContractSemanticModel` per contract, stored in `contracts.semantic`:

- Functions (visibility, mutability, modifiers, params, spans), state variables, inheritance linearization, events.
- External calls and their position relative to state writes.
- Access-control facts: modifiers and their bodies, `msg.sender` comparisons, `hasRole`/`_checkRole`, `Ownable`/`Ownable2Step`/`AccessControl` inheritance.
- Token flows: ETH sends, ERC-20 `transfer`/`transferFrom`/`safeTransfer*`, `_mint`, `_burn`.
- Upgradeability pattern: proxy base classes, `_authorizeUpgrade`, `upgradeTo*`, `delegatecall` sites, initializer functions.
- Contract type classification (`erc20`, `erc4626`, `staking`, `lending`, `other`) by interface and function-signature heuristics.

**Tree-sitter** gives exact spans and resilient parsing; **Slither** gives IR, call graph, and data dependencies. If Slither fails but compile succeeded, degrade gracefully: run Tree-sitter-only extraction and record the limitation in `coverage`.

## Stage 3: Privilege Map (core feature, see `features.md` F1)

Pure deterministic computation:

1. Identify privileged functions: any state-changing function whose reachability from external callers is gated by a sender check (modifier, require, role check).
2. Resolve each guard to a role key.
3. Classify the function's power category from IR facts (rules in `features.md`).
4. Detect mitigations: caps, in-contract delays, two-step transfer, reversibility.
5. Build role graph including `grant/revoke` edges via role admin.
6. Apply any `role_declarations`; compute blast scores and tiers.
7. Fill worst-case sentence from templates. An LLM may rephrase for readability **only** if the rewrite passes a facts-preservation check (same role, power, mitigation words present; no new claims). Default is template text with no LLM.

## Stage 4: Scanning

- Run Slither with a curated detector set (see `detector_map.yaml`: Slither detector ID to `{vuln_class, swc_ids, default_severity}`).
- Run custom detectors in `/packages/detectors` (e.g. unprotected privileged state change, unbounded mint, unchecked upgrade authorization, missing initializer guard).
- Convert results to **candidate findings** with a `static_fact` evidence record containing detector ID, spans, and extracted facts.
- Deduplicate overlapping candidates by `(detector class, function)`.
- Privilege Map results with tier `high`/`critical` and no mitigation produce candidate findings of source `privilege_map` (evidence kind `static_fact`).

## Stage 5: Retrieving (Security RAG, MVP)

Corpus: `security_postmortems` (SWC entries + about 100 curated incidents; see Corpus below).

Per candidate:
1. **Query builder** (fast LLM, structured output): input is a code-free summary of the candidate (vuln class, structural facts such as "external call before state write in withdraw()"); output `{queries: [str], vuln_classes: [str]}`. Never send raw source to the query builder.
2. Qdrant hybrid query: dense + sparse with RRF fusion, `filter: vuln_class in <candidate classes>`, `limit = RAG_TOP_K`.
3. Parent-child expansion: for a hit at chunk level, attach incident summary text.
4. Optional cross-encoder rerank (Milestone 5+).
5. Drop results below `RAG_MIN_SCORE`. No hit is acceptable: the finding keeps its `static_fact` evidence and is labeled "no historical precedent retrieved".

## Stage 6: Synthesizing and Grounding Verifier

LLM drafts `{title, description, scenario, severity_suggestion}` from: candidate facts, minimal code slice, retrieved chunks. Output must parse into a Pydantic model.

**Verifier (deterministic code, runs after every draft):**

| Check | Rule | On failure |
|---|---|---|
| Evidence exists | each cited `chunk_id` resolves in Qdrant/`corpus_documents` | drop citation; if none left and no static_fact, drop finding |
| Quote fidelity | `quote` is exact substring of stored chunk text | strip quote |
| Span validity | every span file+lines exist in manifest | drop finding |
| Fact consistency | named functions/variables in text exist in semantic model | regenerate once, then drop |
| Severity bound | LLM severity may not exceed detector default by more than one level without a deterministic reason | clamp |
| Relevance (optional NLI) | entailment model checks chunk supports claim | demote confidence |
| Injection check | draft text contains no instructions/links not from sources | drop |

Dropped drafts are logged (reason only) and counted for the eval metric `verifier_rejection_rate`.

`llm_hypothesis` findings (no deterministic signal) are allowed only in a separate "Unverified observations" list: `scored=false`, hard-labeled, capped at `info`/`low` display severity.

## Stage 7 and 8: Patching and Verification (M5)

1. Patch planner (reasoning LLM) returns structured `{file, hunks[{old, new}], rationale, behavior_change, storage_layout_impact}`; diff rendered by code, not by the LLM.
2. Apply to a scratch copy in the sandbox. Run: compile, re-run Slither + custom detectors, compare findings, `forge snapshot --diff` for gas if tests exist.
3. Reject if: compile fails, targeted finding not cleared, any new `high`/`critical`, storage layout of upgradeable contract changed, or gas regression exceeds threshold (unless the finding is critical).
4. Up to 3 attempts, each given the previous failure log. After that: guidance text only, no patch.
5. Store patch with full verification results.

## Stage 9: Prove-it (M6)

For findings from detectors in the supported set (reentrancy, access control, unchecked call, simple oracle read), the LLM drafts a Foundry test against the original contract. Run in `sandbox-test` (no network, `ffi = false`). Accept only if: test fails on original, passes on verified patch. Store as `proofs`, add `proof` evidence to the finding, raise confidence. Tests are not exported unless the user opts in.

## Stage 10: Invariants Lite (M7)

Template library `/packages/auditor_core/invariants/templates/{erc20,erc4626,staking,lending}/*.sol.j2` with metadata (`id`, `description`, `applies_if`). Instantiate by contract type, generate handler contracts, run `forge test` invariant mode with bounded runs/depth. A violation yields `counterexample` (call sequence) and an `invariant` finding with `proof` evidence. Templates are human-written and reviewed. LLMs do not author templates at runtime in this phase.

## Stage 11: Reporting

- Heuristic score from verified, scored findings plus privilege-map tiers; weights published in the report.
- `CoverageStatement` always included.
- Exports: JSON, SARIF, Markdown, PDF. Disclaimer in each.

## Corpus (MVP)

Layout: `/corpus/seed/*.yaml`, one file per document:

```yaml
doc_id: swc-107
kind: swc            # swc | postmortem
title: Reentrancy
vuln_class: [reentrancy]
swc_ids: [SWC-107]
source_url: https://...
license: MIT
date: null
loss_usd: null
summary: ...         # our own words
root_cause: ...
exploit_pattern: ...
remediation: ...
excerpts: ["short exact quote <= 300 chars from source, if license allows"]
```

Rules: store our own summaries plus short permitted excerpts and the source URL. Respect each source license. Do not bulk-copy copyrighted reports. Ingestion CLI chunks each doc into `incident` and `chunk` levels, embeds dense + sparse, upserts into Qdrant, mirrors metadata to `corpus_documents`, and stamps `corpus_version`.

## LLM Usage Rules

- All calls go through `LLMClient.structured(schema, messages, model_tier)`; schema-constrained output with validate-and-retry (max 2).
- Source code and corpus text are inserted inside clearly delimited data blocks and the system prompt states they are untrusted data, never instructions.
- Temperature 0 to 0.2. Prompts are versioned files in `/packages/auditor_core/prompts/` with golden tests.
- Record `model_id`, `prompt_version` per audit for reproducibility. Never log prompts or completions.
- Cap tokens per audit; fail soft (skip LLM stages, return deterministic results) when budget exhausted.

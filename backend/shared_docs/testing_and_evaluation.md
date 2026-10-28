# Testing and Evaluation

## 1. Test Pyramid

| Level | Tooling | Scope |
|---|---|---|
| Unit | pytest | Power-category heuristics, scoring math, verifier checks, schema validators, zip safety |
| Integration | pytest + docker compose | DB/RLS, queue, sandbox compile/analysis, Qdrant retrieval |
| Snapshot | pytest + stored JSON | Privilege Map and detector output per fixture |
| API contract | schemathesis against OpenAPI | Status codes, schema conformity |
| Frontend unit | Vitest + Testing Library | Forms, cards, diff viewer |
| E2E | Playwright | Upload to Privilege Map to finding detail to export |
| Security | custom | Sandbox egress, injection, tenant isolation, log scrubbing |
| Eval | `/eval` harness | Retrieval, verifier, detection quality, patch success |

## 2. Fixture Contracts (`/fixtures/contracts`)

Each fixture has `src/`, `expected/privilege_map.json`, `expected/findings.json`, `README.md` describing intent.

| Fixture | Purpose |
|---|---|
| `vault_basic` | Ownable vault with `withdrawAll`, owner mint: baseline Privilege Map |
| `token_accesscontrol` | OZ AccessControl with MINTER/PAUSER, role admin escalation |
| `custom_modifiers` | Custom `onlyAdmin` via mapping and `msg.sender ==` checks |
| `timelocked_admin` | In-contract delay + two-step ownership (mitigation detection) |
| `capped_mint` | `maxSupply` bound (cap detection) |
| `uups_proxy` | `_authorizeUpgrade` gated by owner |
| `renounced_owner` | Ownership renounced in constructor |
| `unguarded_admin` | Privileged write with missing access control |
| `reentrancy_classic` | Classic reentrancy for Slither + RAG evidence + patch |
| `inherited_guards` | Inherited/overridden modifiers |
| `assembly_edge` | Inline assembly (must appear in `undetected_notes`) |
| `mixed_pragmas` | Multiple compiler versions |
| `compile_error` | Must yield `BUILD_FAILED` diagnostics |
| `injection_comments` | Comments with prompt-injection text; verifier must neutralize |
| `zip_bomb`, `zip_traversal` | Upload hardening (generated in test, not committed) |
| `erc4626_vulnerable`, `erc4626_clean` | M7 invariant templates (violated vs passed) |

Snapshot updates require a human-reviewed diff in the PR.

## 3. Critical Unit Tests (must exist)

**Privilege Map**
- Each power-category matcher: positive and negative examples; ambiguous cases fall to `OTHER_PRIVILEGED`.
- Scoring: parameterized table from `features.md` (cap, delay, reversible, holder combinations); delay multiplier not double-counted with declared timelock.
- Role escalation: a role that administers a critical role inherits `0.95 * score`.
- Determinism: shuffle input order, output identical.
- Declaration validation: `threshold <= signers`, unknown role rejected.

**Verifier**
- Quote not substring is stripped; unknown `chunk_id` dropped; finding with no remaining evidence rejected.
- Named function absent from semantic model triggers regenerate-then-drop.
- Severity clamp.
- `llm_hypothesis` never counted in score.

**Security**
- Cross-tenant: org B cannot read org A audit/finding/file (RLS test).
- Sandbox: container cannot reach the network (attempt DNS/HTTP, expect failure).
- Log scrubbing: run fixture, grep logs for unique source strings, expect none.
- Purge: after delete, S3 objects and source-derived rows are gone.

## 4. Evaluation Harness (`make eval`)

Offline by default with recorded LLM responses; `EVAL_LIVE=1` runs against the live provider (nightly job).

| Metric | Dataset | Initial target | Gate |
|---|---|---|---|
| Privilege detection accuracy (role + category) | Labeled fixtures + about 30 open-source contracts labeled by hand | at least 90% on categories, at least 95% on role detection | block on regression |
| Privilege false-positive rate | Same set | under 10% of reported actions | warn |
| Static finding precision (High/Critical) | Audited-clean production contracts | at least 70% | warn |
| Static recall by class | Known-vulnerable benchmarks (SmartBugs-style curated set, DeFiHackLabs reproductions, public contest findings) | track per class | block on regression |
| Retrieval recall@5 | Hand-labeled (finding, correct source) pairs, at least 100 | at least 0.85 | block |
| Unsupported-claim rate | Verifier-audited sample of outputs | under 1% | **block** |
| Verifier rejection rate | Same | tracked, alert on spikes | warn |
| Patch success (compile + cleared + no new high/critical) | Fixtures + benchmark | at least 70% on supported classes | warn |
| Gas regression | `forge snapshot` before/after | median delta <= 0 | warn |
| Proof validity (M6) | Supported detectors | at least 80% produce fails-then-passes tests | warn |
| Invariant templates (M7) | `*_vulnerable` vs `*_clean` fixtures | 100% violated/passed as labeled | block |
| End-to-end latency | 500-line contract | p50 under 3 min with LLM stages | warn |

**Contamination control:** keep a hold-out set of incidents newer than the corpus and not published in common training-era datasets; report scores on hold-out separately. Frontier models have likely seen public post-mortems, so do not treat benchmark scores as evidence of generalization.

**Coverage honesty check:** for each eval contract, record what the tool declared as "not analyzed" and compare against known gaps. Report the percentage of known gaps correctly disclosed.

## 5. CI Pipeline

1. **Pre-commit:** ruff, mypy, eslint, prettier, secret scan, no-customer-code-in-logs lint.
2. **PR:** unit + integration + snapshot + API contract + frontend tests; image build and scan.
3. **PR (if prompts, corpus, detectors, or scoring changed):** offline eval, results posted as a PR comment, gates enforced.
4. **Nightly:** live-LLM eval, hold-out set, sandbox escape/egress tests, dependency scan.
5. **Release:** staged deploy, smoke test (upload `vault_basic`, assert Privilege Map snapshot), corpus version stamped.

## 6. Test Data Policy

- Fixtures are original or properly licensed; no real customer code ever enters the repo or eval sets.
- Eval corpora of real contracts use public, open-licensed code with provenance recorded.
- Recorded LLM responses contain no customer data.

## 7. Definition of Done for a Milestone

All milestone tasks complete; relevant tests green; eval gates for affected metrics pass; docs updated; security checklist items for the milestone verified (see `build_plan.md`).

# Feature Specs (for developers)

Each feature lists: user story, inputs, outputs, algorithm, acceptance criteria, edge cases.

---

## F0: Project, Upload and Audit Lifecycle (P0)

**Story:** As a developer I upload my contracts, start an audit, and watch progress.

**Inputs:** `.sol` file(s) or `.zip` (Foundry/Hardhat project), optional compiler version override, optional role holder declarations.
**Outputs:** `Audit` with status, live events, report.

**Acceptance criteria**
- Upload up to `MAX_UPLOAD_MB`; zip is validated (no traversal/symlinks).
- Audit creation returns `202` with `audit_id` in under 500 ms; work happens in the worker.
- SSE stream shows each stage start/end and ends with a terminal event.
- Compile failure surfaces diagnostics and a clear message, never a blank error.
- User can cancel a running audit and delete an audit (immediate purge).

**Edge cases:** mixed pragmas; missing imports; very large files; duplicate filenames in different folders; empty project; non-Solidity upload; compile succeeds but Slither crashes (degrade, note in coverage).

---

## F1: Privilege Map ("Who can rug me?") (P0, flagship)

**Story:** As a founder I see which roles can do dangerous things, what the worst case is, and what limits abuse, so I can fix centralization risk before launch.

**Inputs:** semantic model, optional `role_declarations`.
**Outputs:** `PrivilegeMap` (roles, powers, edges, scores, worst-case text, undetected notes).

### Power taxonomy (fixed)

| Category | Detection heuristic (from IR / AST) | Base score |
|---|---|---|
| `SELFDESTRUCT_OR_DELEGATECALL` | `selfdestruct`, or `delegatecall` to non-constant/param address in guarded fn | 100 |
| `UPGRADE` | `_authorizeUpgrade`, `upgradeTo*`, `changeAdmin`, beacon `upgradeTo`, writes to implementation slot | 95 |
| `WITHDRAW_FUNDS` | guarded fn sends ETH/tokens to arbitrary or caller-chosen address not derived from user balance accounting | 90 |
| `MINT` | guarded call to `_mint` or increments `totalSupply`/balances for arbitrary address | 85 |
| `CHANGE_ORACLE` | guarded write to a state var later used as oracle/price source address | 80 |
| `BURN_OTHERS` | guarded `_burn`/balance decrease of an address other than caller | 75 |
| `BLACKLIST_FREEZE` | guarded write to a mapping read in transfer path (revert/block) | 70 |
| `GRANT_ROLE` | `grantRole`/`revokeRole`/`transferOwnership`/custom admin-set functions | 60 |
| `CHANGE_FEE` | guarded write to var used in fee computation | 55 |
| `CHANGE_PARAMETER` | other guarded write to a var read by value-moving fns | 45 |
| `PAUSE` | guarded write to a flag checked by `whenNotPaused`/similar | 40 |
| `OTHER_PRIVILEGED` | guarded state change not matching above | 30 |

Heuristics are implemented as separate, unit-tested functions, one per category, each returning `(matched: bool, facts: dict)`. Unclear matches must fall back to `OTHER_PRIVILEGED`, not guess.

### Role resolution
- `Ownable`/`Ownable2Step` gives role `OWNER`.
- OpenZeppelin `AccessControl`: each `bytes32` role constant becomes a role; `DEFAULT_ADMIN_ROLE` is the default admin of each role unless `_setRoleAdmin` changes it.
- Custom modifiers: inspect modifier body for `msg.sender == X`, `require(isX[msg.sender])`, `hasRole(...)`; role key `CUSTOM:<modifier name>`.
- Proxies: UUPS authorizer function guard; Transparent proxy admin gets `PROXY_ADMIN`.
- Unguarded functions that perform privileged-category writes are **not** in the map; they raise a separate "missing access control" candidate finding.

### Mitigation detection
- **Cap/bound:** `require(x <= CONSTANT)`, `maxSupply`/`cap()` checks, `ERC20Capped`. Record the bound if constant.
- **Delay:** in-contract timelock pattern (`queue/execute` with timestamp comparison, `TimelockController` inheritance, `pendingX` + `effectiveAt` patterns). Record seconds if constant.
- **Two-step:** `Ownable2Step`/pending-owner accept pattern.
- **Reversible:** counterpart function exists and is guarded equally (e.g. `unpause`).

### Blast score

```
action_score = base[category]
             * (0.6  if cap_detected else 1.0)
             * delay_mult(max(in_contract_delay, declared_delay))   # >=24h: 0.5, >=1h: 0.75, else 1.0
             * (0.85 if reversible else 1.0)
             * holder_mult(declaration)                              # see table
role_score   = max(action_score over role's actions,
                   0.95 * role_score(r) for each role r this role can grant/administer)
tier         = critical>=80, high 60-79, medium 35-59, low 1-34, none 0
```

| Holder declaration | `holder_mult` | Notes |
|---|---|---|
| none given (default) / `eoa` | 1.0 | `holder_assumed = true` when none given |
| `contract_unknown` | 0.9 | |
| `multisig` threshold>=2, signers>=3 | 0.7 | |
| `multisig` threshold>=3, signers>=5 | 0.6 | |
| `timelock_multisig` delay>=24h | 0.4 | delay multiplier not applied twice, use the lower |
| `renounced` | 0.0 | user-asserted; marked "unverified" |

All numbers live in `scoring_config.yaml` and are covered by snapshot tests. The weights are shown in the UI "How is this scored?" drawer.

### Worst-case text (template-based)
Templates keyed by category, filled with facts, e.g.:
`"{role} can mint {unbounded|up to {cap}} tokens to any address {with no delay|after a {delay} delay}."`
Always append a mitigation sentence: "No timelock, no cap, no multisig assumed." or "Declared: 3-of-5 multisig, 48h timelock."

### Holder declaration UX
Optional panel per role: EOA / multisig (threshold, signers) / timelock + multisig (delay) / renounced / unknown contract. Changing a declaration recomputes the map synchronously (no worker needed) and updates scores live. Results carry the label **"Holder not declared: assuming single key"** until declared.

### Acceptance criteria
- Detects `onlyOwner`, OZ `AccessControl`, and custom-modifier gating on fixtures (see `testing_and_evaluation.md`).
- For `fixtures/contracts/vault_basic`, snapshot matches: roles, categories, scores.
- Role-admin escalation raises a lower role's score (test: MINTER admin'd by DEFAULT_ADMIN).
- Recomputation after declaration change in under 300 ms on a 2,000-line project.
- Deterministic: same input gives identical output (stable ordering).
- Every high/critical, unmitigated result produces a candidate finding with `static_fact` evidence.
- `undetected_notes` lists known blind spots hit (e.g. "assembly block at L88 not analyzed", "role assigned via external contract not resolved").

### Edge cases
Inherited modifiers; overridden functions; modifiers calling internal helpers; role checked in an internal function (not a modifier); `msg.sender` aliasing to a local variable; multiple owners via mapping; ownership already renounced in constructor; roles granted in constructor to `address(this)`; function pointers and low-level calls (mark as not analyzed); proxies where implementation is not provided (limit analysis, note in coverage); interfaces and abstract contracts (analyze only concrete, report abstract guards as inherited).

---

## F2: Static Findings (P0/P1)

**Story:** I see standard vulnerability findings ranked by severity with exact code locations.

**Algorithm:** Slither detectors + custom detectors, mapped via `detector_map.yaml`, deduplicated, converted to findings with `static_fact` evidence (see pipeline Stage 4).

**Acceptance:** each finding has title, severity, confidence, span(s), description, at least one evidence record; false-positive dismissal persists (`status=dismissed`) and is excluded from score.

**Edge cases:** detector noise on OpenZeppelin or vendored libs (mark `is_dependency`, exclude from findings by default, optionally include); duplicate findings across inheritance; test/mocks folder excluded by default.

---

## F3: Security RAG Evidence (P1)

**Story:** Each finding shows real historical precedent (SWC entry or incident) with a link and a quote.

**Acceptance**
- Finding detail shows up to 3 evidence cards: title, locator, link, exact quote, relevance score.
- No evidence retrieved: card says "No historical precedent retrieved" and the `static_fact` evidence remains.
- Verifier rejects any citation whose quote is not an exact substring of the stored chunk.
- Retrieval golden set recall@5 at least 0.85 (see testing doc).

**Edge cases:** multi-class findings; empty corpus; Qdrant unavailable (degrade: skip retrieval, mark audit with a coverage note); stale `corpus_version` recorded in the report.

---

## F4: Patch Generator and Verifier (P1)

**Story:** I get a red/green diff that fixes the issue, compiles, and does not introduce new findings or large gas regressions.

**Acceptance:** patches only offered when verified (compile + target finding cleared + no new high/critical); show gas delta when tests exist, else "gas not measured"; "Edit and re-verify" re-runs verification on user edits; patch for upgradeable contracts blocked if storage layout changes (explain why).

**Edge cases:** patch touches multiple files; fix requires a new import/dependency (allow only OpenZeppelin already in project); conflicting patches for two findings (apply sequentially in a scratch copy; report conflicts); solc version incompatibility.

---

## F5: Prove-It Exploit Tests (P2)

**Story:** For supported findings, I see a runnable test that exploits the bug on my original code and fails on the patched code.

**Acceptance:** only for supported detector classes; test fails on original and passes on patched copy, else no proof is shown; test source viewable and copyable; badge "Proven" on the finding, raises confidence; never executed outside `sandbox-test`; tests not included in default exports.

**Edge cases:** contracts needing complex setup (constructor args, external deps); tests that pass trivially (check the test asserts an attacker profit or invariant break); flaky tests (run twice).

---

## F6: Invariant Hunter Lite (P2)

**Story:** For common contract types, standard invariants are checked automatically, and violations come with a concrete call sequence.

**Template catalog (initial)**
- `erc20`: total supply equals sum of balances (bounded accounts); transfer cannot increase sender balance; no unauthorized mint.
- `erc4626`: `previewRedeem(previewDeposit(x)) <= x`; share price does not decrease on deposit/withdraw (excluding fees); no user withdraws more than assets owned by shares.
- `staking`: rewards claimed <= rewards funded; stake/unstake round trip does not gain.
- `lending`: total debt <= total collateral value * max LTV (when oracle mocked); liquidation cannot make a healthy position insolvent.

**Acceptance:** contract type classified with a confidence value; user can confirm or override type; each template run shows `passed | violated | error | skipped (reason)`; violated gives a minimal call sequence; templates reviewed by a human and covered by known-buggy and known-good fixtures.

**Edge cases:** non-standard decimals; fee-on-transfer tokens; contracts requiring complex deployment wiring (mark `skipped`, never guess); inherited behaviors.

---

## F7: Report and Export (P1)

**Acceptance:** JSON, Markdown, SARIF (findings only), PDF; every export contains the disclaimer, coverage statement, toolchain and corpus versions, privilege map summary, scoring weights.

---

## Deferred (do not build yet)

Regulatory RAG (Collection B), jurisdiction toggle, compliance findings, cross-jurisdiction conflict notes, regulatory corpus pipeline. Schema and UI have reserved extension points only (`findings.category` check, `regulatory_clauses` collection name). When compliance is built, it must be framed as "mechanics flags plus questions for counsel", never as violations.

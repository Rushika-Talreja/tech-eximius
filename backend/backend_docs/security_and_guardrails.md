# Security and Guardrails

This product receives unreleased, potentially vulnerable code. Treat the platform as a high-value target.

## 1. Threat Model (summary)

| Threat | Vector | Mitigation |
|---|---|---|
| Remote code execution via uploaded project | npm postinstall, Hardhat/Foundry scripts, FFI cheatcodes, malicious git submodules | Never run user scripts; `npm ci --ignore-scripts`; `ffi=false`; compile in no-network sandbox; only generated tests run (M6+) |
| Sandbox escape | Kernel/container exploit | Non-root, read-only rootfs, seccomp, dropped capabilities, cgroup limits, gVisor in prod, one job per container, destroyed after use |
| Supply-chain attack in dependency fetch | Malicious package/repo | Allowlist registries, no secrets in fetch container, pinned hashes where possible, scan archives, fetch isolated from analysis |
| Zip bombs / path traversal | Crafted archives | Size/ratio/file-count limits, reject `..`, absolute paths, symlinks |
| Prompt injection from code | Comments, strings, identifiers ("ignore previous instructions") | Code is untrusted data in delimited blocks; structured outputs only; deterministic verifier; LLM never has tools or network |
| Prompt injection from corpus | Poisoned scraped text | Curated corpus, human review, hash-pinned ingestion, strip instructions/links during ingestion |
| Data leak to LLM provider | Code sent to third party | Zero-retention/no-training contracts, provider allowlist, option for self-hosted model, minimize code sent (slices, not whole projects) |
| Cross-tenant access | Missing org filter | Postgres RLS, org-scoped queries, automated isolation tests |
| Credential theft | Leaked keys | Secrets in a manager, never in images/logs; API keys hashed with pepper; short-lived signed URLs |
| Score abuse as trust badge | Founders market "92/100" | Heuristic label, coverage statement on every export, no badge feature, terms of use forbidding marketing as certification |
| Misuse for exploit development | Using exploit-test feature offensively | Exploit tests only against submitted code in sandbox, not exported by default, rate limits, no step-by-step weaponized writeups |
| Honeypot risk | Store of unpatched vulns | Short retention (default 24 h), encryption at rest with per-tenant keys, access audit logs, purge verification |

## 2. Sandbox Specification

```
docker run --rm
  --network none
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m
  --cpus=$SANDBOX_CPU_LIMIT --memory=${SANDBOX_MEM_LIMIT_MB}m --pids-limit=256
  --cap-drop=ALL --security-opt=no-new-privileges
  --user 10001:10001
  -v deps:/deps:ro -v src:/src:ro -v out:/out:rw
  --runtime=$SANDBOX_RUNTIME   # runsc in staging/prod
  sandbox-analysis <command>
```
- Hard wall-clock timeout (`SANDBOX_TIMEOUT_SECONDS`) with forced kill.
- Output size cap on `/out`; only whitelisted file names collected.
- Foundry config for generated tests: `ffi = false`, `fs_permissions = []`.
- Analysis images built from pinned base digests and scanned in CI.

## 3. Hallucination Control (hard rules)

1. `Finding.evidence` has `min_length=1`; DB service layer refuses writes otherwise.
2. Evidence kinds: `static_fact` (deterministic detector output), `swc`/`postmortem` (retrieved, quote verified), `proof` (reproduced test).
3. Quotes must be exact substrings of stored chunks (string match, not LLM judgment).
4. Named functions/variables in generated text must exist in the semantic model.
5. LLM-only observations are `llm_hypothesis`: unscored, separate list, clearly labeled, severity capped.
6. Patches are shown only if empirically verified (compile, re-scan, no new high/critical).
7. Retrieval below threshold produces "no precedent retrieved", never a stretched citation.
8. Eval gate: unsupported-claim rate on the golden set must stay under 1% or the release is blocked.

## 4. Code Confidentiality

- **Never** embed customer code into Qdrant or any shared index. Queries use code-free abstractions (class, structural facts).
- LLM requests: send minimal slices; provider contract must state no retention and no training; `LLM_ZERO_RETENTION=true` enforced at startup in staging/prod (app refuses to start otherwise).
- Encryption: TLS 1.3 in transit; per-tenant KMS keys for object storage; database volume encryption.
- Retention: default 24 h (`DEFAULT_RETENTION_HOURS`), configurable down to 1 h; user delete purges immediately; purge job verifies object deletion and logs an audit record (IDs and timestamps only).
- Logging: structured logs contain IDs/hashes/timings only. A log filter drops fields named `source`, `code`, `diff`, `prompt`, `completion`. CI has a test that runs an audit on a fixture and greps logs for fixture-unique strings.
- Error tracking (Sentry etc.) uses `before_send` scrubbing and no request bodies.
- Support access to customer audits requires explicit customer consent and is logged.
- Optional later: self-hosted/BYOC deployment for sensitive customers.

## 5. Advisory Scope and Required Wording

Standard disclaimer (single constant, shown in UI, API `disclaimer` field, and all exports):

> This report is generated by an automated advisory tool. It does not guarantee the security of any smart contract, does not constitute a formal audit, and is not legal advice or a certification of regulatory compliance. Consult qualified security auditors and legal counsel before deployment.

Rules:
- Never state or imply "safe", "secure", "audited", "certified", or "compliant".
- A clean result is worded: "No verified issues detected by this analysis" plus the coverage statement.
- Score is always labeled "heuristic risk indicator".
- Privilege Map results labeled `holder assumed` until declared; declarations are user-asserted and shown as such.

## 6. Scope Boundaries (enforced)

- Pre-deployment source analysis only. No RPC connections to chains, no mempool access, no wallet clustering, no transaction monitoring.
- Requests classified as out of scope (e.g. "trace this wallet", "monitor this address") return `OUT_OF_SCOPE` with an explanation.
- Compliance/regulatory analysis is deferred; if reintroduced it must be mechanics flags plus questions for counsel, never violation verdicts, and must pass legal review.

## 7. Authentication, Authorization, Abuse Controls

- Short-lived OIDC JWTs; API keys scoped, hashed (`HMAC-SHA256` with pepper), prefix-identifiable, revocable, last-used tracked.
- Rate limits per org and per key: audits per hour, upload size, concurrent audits; global LLM budget per audit.
- Request validation with strict Pydantic models; reject unknown fields on write endpoints.
- CORS locked to the web origin; CSRF protection on cookie-authenticated proxy routes (same-site cookies + origin check).
- Security headers on web app (CSP, HSTS, `X-Content-Type-Options`, `frame-ancestors none`).

## 8. Secure SDLC

- Dependency and container vulnerability scanning in CI; SBOM generation; signed images.
- Secret scanning in pre-commit and CI.
- Threat-model review at each milestone gate; red-team tests: prompt injection fixtures, zip-bomb fixtures, malicious `package.json` fixtures, sandbox network-egress test (must fail).
- Incident response runbook: key rotation, tenant data purge, customer notification template.

## 9. Compliance of the Platform Itself (later)

Target SOC 2 Type II controls (access control, change management, logging, retention). Data processing agreement template covering LLM subprocessors. Terms of use: advisory only, no use as certification or marketing badge, no reliance for legal compliance.

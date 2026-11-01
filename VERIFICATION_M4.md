# Milestone M4 Verification Report: Evidence Workstream

**Review Date:** October 28, 2026  
**Target Branch:** `angel-m4` (commit `179f0f3` by Angel Aggarwal)  
**Review Type:** Read-Only Independent Review  
**Auditor:** Independent Architecture & Verification Reviewer  

---

## 1. Verdict

**Verdict:** **REJECT**  
**Reason:** The evidence workstream cannot be accepted in its current state because the core functional deliverables—including the grounding verifier, production hybrid retrieval, evaluation golden set, and detector map—were left completely unimplemented or replaced with a 9-line mock stub. Additionally, the submitted work was isolated into an unintegrated `defi/` subdirectory containing committed binary databases and personal Windows paths rather than conforming to the repository's monorepo architecture.

---

## 2. Deliverable Scorecard

| Deliverable | Status | Summary Assessment |
| :--- | :---: | :--- |
| **Corpus (`corpus/seed/*.yaml`)** | **PARTIAL** | Only 12 of 35+ required SWC entries provided; 0 of ~100 incident postmortems provided. 7 of 12 entries use unagreed or provisional vulnerability classes. However, summaries are well-written original prose with no copyright infringement (max shared word run with live sources $\le 3$ words). |
| **Ingestion CLI (`auditor.corpus`)** | **PARTIAL** | Core chunking into taxonomy/incident/chunk levels and upserting dense (`BAAI/bge-small-en-v1.5`, 384d) + sparse (`Qdrant/bm25`) vectors into `security_postmortems` works idempotently. However, database mirroring to `corpus_documents` and `corpus_version` stamping are missing. |
| **Retrieval Engine (`retrieve_evidence`)** | **FAIL** | Completely unimplemented. Replaced with `defi/fake_retrieve.py`, a 9-line mock stub returning a hardcoded DAO dictionary. Yielded 0.00 recall@5 and 0.00 negative rejection rate across 25 independent benchmark queries. Hybrid fusion, parent-child expansion, score thresholding, and fail-soft are absent. |
| **Detector Map (`detector_map.yaml`)** | **FAIL** | Completely missing. Stage 4 scanning engine expects `packages/auditor_core/rag/detector_map.yaml`. Only a 10-line script reading raw `slither_out.json` was provided. |
| **Grounding Verifier (`verify_draft`)** | **FAIL** | Completely unimplemented (0 of 10 verification rules implemented). The pipeline Stage 6 gate cannot run. |
| **Evaluation Artifacts (`eval/retrieval/`)** | **FAIL** | Completely missing. 0 golden-set query pairs provided (100+ required), no recall@5 evaluation script, no negative query suite, and no hold-out benchmark set. |
| **Interfaces (`interfaces.py` Conformance)** | **FAIL** | Deliverable does not expose `retrieve_evidence(candidate: CandidateSummary) -> RetrievalResult` or `verify_draft(...)`. Instead, a standalone script with incompatible parameter types `(description, filters)` was created. |
| **Scope, Hygiene & Repository Layout** | **FAIL** | Work was placed in an unauthorized `defi/` directory outside the monorepo structure. Committed a 315 KB SQLite binary database (`storage.sqlite`), lock files, egg-info artifacts, and personal Windows filesystem paths (`C:\Dev\defi`). Ruff check failed with 8 errors. |

---

## 3. Empirical Verification Numbers

### Corpus Metrics
- **Total YAML Files Found:** 12
- **SWC Definitions:** 12 (Target: $\ge 35$) $\rightarrow$ **FAIL**
- **Incident Postmortems:** 0 (Target: $\approx 100$) $\rightarrow$ **FAIL**
- **Schema Validation Failures:** 0 (All 12 files contain required fields)
- **Agreed Taxonomy Compliance:** 5 files compliant, 7 files with provisional/unagreed classes
- **Max Excerpt Length:** All $\le 300$ chars (PASS)
- **Max Field Length:** All $\le 1,200$ chars (PASS)
- **Near-Duplicates / Duplicate URLs:** 0 detected
- **Prompt Injections / Foreign URLs:** 0 detected

### Retrieval Benchmark (25 Independent Queries)
Tested via `tests/verification/test_retrieval_behavior.py` (20 positive across 8 vulnerability classes, 5 negatives):
- **Developer Deliverable Recall@5:** **0.00** (Gate Target: $\ge 0.85$)
- **Developer Deliverable Precision@3:** **0.00**
- **Negative Rejection Rate:** **0.00** (Target: 1.00; `fake_retrieve` returned the DAO dictionary for all 5 negative queries, including pancake recipes and CSS questions)
- **Hybrid Search vs Dense vs Sparse:** NOT VERIFIABLE on her module (no hybrid or sparse query pipeline implemented in `fake_retrieve.py`)
- **Parent-Child Expansion:** NOT IMPLEMENTED
- **Fail-Soft on Qdrant Outage:** FAIL (Mock does not connect to Qdrant and has no degraded state)

### Ingestion Performance & Storage
- **Ingestion Dry Run:** 60 records generated from 12 documents in 0.08s
- **Vector Space Configuration:**
  - Dense Vector: `dense`, 384 dimensions, Cosine distance
  - Sparse Vector: `bm25`, Qdrant BM25 index
- **Total Points in Pre-committed Collection:** 60 points
- **Point Breakdown:** 12 taxonomy, 12 incident, 36 chunk records
- **Payload Indexes in Local Path Mode:** 0 (`payload_schema: {}`)
- **Idempotency (Unit Test `test_ingest.py`):** 5 passed in 3.45s (0 added, 0 updated, 5 skipped on re-run)

### Test Suite & Code Quality
- **Unit Tests Provided:** 5 tests in `defi/tests/test_ingest.py` (All 5 passed using `StubEmbedder`)
- **Ruff Lint Errors:** 8 errors across 3 files (`F401`, `I001`, `SIM115`, `BLE001`, `UP035`, `RUF022`)
- **MyPy:** Blocked without workaround due to hard top-level `fastembed` import on Python 3.13 macOS

---

## 4. Comprehensive Findings List

### Finding 1: Grounding Verifier Completely Unimplemented (Stage 6 Gate)
- **Severity:** **BLOCKER**
- **Location:** `packages/auditor_core/auditor_core/interfaces.py:84-93` / `defi/` (missing)
- **Evidence:**  
  The verifier deliverable was not submitted. Neither `defi/` nor `packages/auditor_core` contains an implementation of `verify_draft`. None of the 10 critical security checks exist:
  - Exact quote substring verification
  - Cited `chunk_id` resolution
  - Manifest file and span boundary checks
  - Semantic model function/state consistency
  - Severity clamping to detector default $+1$
  - Injection pattern detection in drafts
  - Model-only hypothesis rerouting to unscored observations
  Running `tests/verification/test_verifier_adversarial.py` confirmed 0 of 10 rules passed.
- **Suggested Fix:** Implement `verify_draft(draft, chunks, model, manifest) -> FindingDraft | None` in `packages/auditor_core/auditor_core/verifier/` implementing the deterministic checks defined in Stage 6 of `analysis_pipeline.md` and Section 3 of `security_and_guardrails.md`.

---

### Finding 2: Production Evidence Retrieval Replaced by Static Mock Stub
- **Severity:** **BLOCKER**
- **Location:** `defi/fake_retrieve.py:1-9`
- **Evidence:**  
  ```python
  def retrieve(description, filters=None):
      return [{
          "id": "dao-2016",
          "title": "The DAO hack",
          "description": "Re-entrancy: ETH sent before balance updated, about $60M lost.",
          "source_url": "https://example.com/placeholder",
          "score": 0.9,
      }]
  ```
  The developer did not build the retrieval engine connecting to Qdrant. On 25 independent queries, Recall@5 was 0.00 and Negative Rejection Rate was 0.00.
- **Suggested Fix:** Implement `retrieve_evidence(candidate: CandidateSummary) -> RetrievalResult` in `packages/auditor_core/auditor_core/rag/retrieval.py` performing:
  1. Qdrant hybrid query (`dense` + `bm25` with reciprocal rank fusion).
  2. Filtering by `vuln_class in candidate.vuln_classes`.
  3. Parent-child expansion (attaching parent incident text to chunk hits).
  4. Score thresholding (default 0.35).
  5. Returning typed `Evidence` objects with exact quote verification.
  6. Soft degradation (`degraded=True`) when Qdrant is unreachable.

---

### Finding 3: Evaluation Golden Set and Recall Harness Missing
- **Severity:** **BLOCKER**
- **Location:** `eval/retrieval/` (empty)
- **Evidence:**  
  The repository contains no golden-set pairs, no recall script, and no negative validation query set. The milestone evaluation gate requiring recall@5 $\ge 0.85$ on 100+ labeled pairs cannot be measured or enforced.
- **Suggested Fix:** Author `eval/retrieval/golden_set.yaml` containing at least 100 labeled query-to-source pairs across all agreed vulnerability classes, include 20+ negative queries, and provide `eval/retrieval/run_eval.py` to calculate recall@5 and precision@3.

---

### Finding 4: Slither `detector_map.yaml` Missing
- **Severity:** **BLOCKER**
- **Location:** `packages/auditor_core/auditor_core/rag/detector_map.yaml` (missing)
- **Evidence:**  
  Pipeline Stage 4 (`scanner.py:68`) explicitly looks for `packages/auditor_core/rag/detector_map.yaml` to map Slither detector IDs to vulnerability classes and SWC IDs. In `angel-m4`, no detector map was committed; instead, an ad-hoc 10-line script `defi/read_slither.py` reading `slither_out.json` was provided.
- **Suggested Fix:** Create `packages/auditor_core/auditor_core/rag/detector_map.yaml` mapping all 15 curated Slither detectors (`reentrancy-eth`, `unchecked-lowlevel`, `tx-origin`, `controlled-delegatecall`, `suicidal`, etc.) to their agreed `vuln_class` and SWC ID.

---

### Finding 5: Incomplete Corpus and Non-Standard Taxonomy
- **Severity:** **MAJOR**
- **Location:** `defi/corpus/seed/*.yaml`
- **Evidence:**  
  - Only 12 SWC files were written (requirement: 35+ SWC entries).
  - 0 incident postmortem files were written (requirement: $\approx 100$ incidents).
  - 7 files use provisional or unagreed class names:
    - `swc-101`: `integer-overflow` (not in agreed list)
    - `swc-104`: `unchecked-call` (singular vs agreed `unchecked-calls`)
    - `swc-110`: `assertion-failure` (not in agreed list)
    - `swc-114`: `transaction-ordering` (not in agreed list)
    - `swc-116`: `timestamp-dependence` (not in agreed list)
    - `swc-120`: `weak-randomness` (not in agreed list)
    - `swc-135`: `dead-code` (not in agreed list)
- **Suggested Fix:** Expand the corpus to 35+ SWC files and ~100 incident postmortems. Map all entries to the 10 agreed vulnerability classes in `severity_defaults.yaml` (`reentrancy`, `unchecked-calls`, `access-control`, `delegatecall`, `uninitialized-state`, `uninitialized-storage`, `upgrade-safety`, `tokenomics-logic`, `initialization`, `centralization-risk`).

---

### Finding 6: Work Placed in Unauthorized Subdirectory `defi/`
- **Severity:** **MAJOR**
- **Location:** `defi/`
- **Evidence:**  
  The workstream brief explicitly designated: *"Owns ONLY packages/auditor_core/rag/, corpus/, eval/retrieval/"*. The developer built a completely separate project structure inside `defi/` with its own `pyproject.toml`, `requirements.txt`, and isolated paths.
- **Suggested Fix:** Move all files out of `defi/` into the canonical monorepo paths:
  - `defi/packages/auditor_core/rag/*` $\rightarrow$ `packages/auditor_core/auditor_core/rag/`
  - `defi/corpus/seed/*` $\rightarrow$ `corpus/seed/`
  - Remove the `defi/` directory entirely.

---

### Finding 7: Ingestion Pipeline Missing DB Mirroring and Corpus Versioning
- **Severity:** **MAJOR**
- **Location:** `defi/packages/auditor_core/rag/ingest.py:270-360`
- **Evidence:**  
  `ingest.py` only talks to Qdrant. It does not synchronize records with the PostgreSQL `corpus_documents` table and does not compute or stamp `corpus_version` as required by the pipeline specification.
- **Suggested Fix:** Add a database session parameter to `ingest()` to mirror document metadata into `corpus_documents`, compute the SHA-256 digest across all corpus files as `corpus_version`, and record it in the database.

---

### Finding 8: Binary SQLite Database and Build Artifacts Committed to Git
- **Severity:** **MAJOR**
- **Location:** `defi/qdrant_data/collection/security_postmortems/storage.sqlite`, `defi/packages/defi_auditor.egg-info/`
- **Evidence:**  
  A 315 KB SQLite binary file (`storage.sqlite`), lock file (`.lock`), metadata JSON, and setuptools `egg-info` directories were committed to version control.
- **Suggested Fix:** Delete `defi/qdrant_data/` and `defi/packages/*.egg-info/` from git tracking using `git rm -r --cached` and add them to `.gitignore`.

---

### Finding 9: Top-Level Fastembed Import Breaks Python 3.13 Compatibility
- **Severity:** **MAJOR**
- **Location:** `defi/packages/auditor_core/rag/ingest.py:21`, `defi/pyproject.toml:9`
- **Evidence:**  
  `ingest.py` imports `fastembed` at the top level. `fastembed==0.9.1` requires `onnxruntime`, which publishes no binary wheels for Python 3.13 on macOS. When running pytest, collection failed immediately with `ModuleNotFoundError: No module named 'fastembed'`.
- **Suggested Fix:** Enforce Python 3.12 per `AGENTS.md` (`requires-python = ">=3.12, <3.13"`). Additionally, make embedding imports lazy within `Embedder.__init__()` so lightweight operations (dry-run, tests with stubs, schema validation) do not require heavy native ONNX runtime dependencies.

---

### Finding 10: Hardcoded Personal Windows Path
- **Severity:** **MINOR**
- **Location:** `defi/check_seed.py:1`
- **Evidence:**  
  ```python
  """Run from C:\\Dev\\defi:  python check_seed.py
  Stage 1 checks every YAML in corpus/seed. Stage 2 checks what is in local Qdrant."""
  ```
- **Suggested Fix:** Remove user-specific hardcoded paths from docstrings and scripts.

---

### Finding 11: Ruff Lint Violations (8 Errors)
- **Severity:** **MINOR**
- **Location:** `defi/check_seed.py`, `defi/packages/auditor_core/rag/ingest.py`, `defi/tests/test_ingest.py`
- **Evidence:**  
  `ruff check defi/` reports 8 errors:
  - `defi/check_seed.py:3:18`: `F401` unused import `sys`
  - `defi/check_seed.py:3:1`: `I001` unformatted import block
  - `defi/check_seed.py:17:28`: `SIM115` open file without context manager
  - `defi/check_seed.py:18:12`: `BLE001` blind exception catch
  - `defi/check_seed.py:60:8`: `BLE001` blind exception catch
  - `defi/packages/auditor_core/rag/ingest.py:18:1`: `UP035` deprecated `typing.Sequence`
  - `defi/packages/auditor_core/rag/ingest.py:26:11`: `RUF022` unsorted `__all__`
  - `defi/tests/test_ingest.py:1:1`: `I001` unformatted import block
- **Suggested Fix:** Run `ruff check --fix` and replace unclosed file handles with `with open(...)` blocks.

---

## 5. Manual Source Verification Guide for User

We audited all 12 submitted SWC documents with fixed seed 42. Every URL was fetched over live HTTP and returned status 200. Longest shared word sequences with live sources were 1 to 3 words, confirming genuine human summarization rather than verbatim copying.

Please manually spot-check these 12 entries against their live documentation:

| # | Doc ID | Title | Live Source URL | What to Check Against Source |
|---|---|---|---|---|
| 1 | `swc-120` | Weak Sources of Randomness | [SWC-120 Docs](https://swcregistry.io/docs/SWC-120) | Confirm whether `block.prevrandao`, `block.timestamp`, and `blockhash` limitations match the summary. |
| 2 | `swc-104` | Unchecked Call Return Value | [SWC-104 Docs](https://swcregistry.io/docs/SWC-104) | Confirm that the distinction between low-level `call()`/`send()` and Solidity `transfer()` is accurately reflected. |
| 3 | `swc-101` | Integer Overflow and Underflow | [SWC-101 Docs](https://swcregistry.io/docs/SWC-101) | Confirm that Solidity 0.8+ built-in overflow checking is accurately cited in remediation. |
| 4 | `swc-107` | Reentrancy | [SWC-107 Docs](https://swcregistry.io/docs/SWC-107) | Verify the description of CEI (Checks-Effects-Interactions) and reentrancy locks. |
| 5 | `swc-106` | Unprotected SELFDESTRUCT | [SWC-106 Docs](https://swcregistry.io/docs/SWC-106) | Confirm that access control recommendations on `selfdestruct` match SWC remediation advice. |
| 6 | `swc-135` | Code With No Effects | [SWC-135 Docs](https://swcregistry.io/docs/SWC-135) | Verify that dead expressions (e.g. `msg.sender == owner;` without `require`) are accurately described. |
| 7 | `swc-112` | Delegatecall to Untrusted Callee | [SWC-112 Docs](https://swcregistry.io/docs/SWC-112) | Confirm context-preservation risks (storage collisions, caller privileges) are accurately stated. |
| 8 | `swc-116` | Block Values as a Proxy for Time | [SWC-116 Docs](https://swcregistry.io/docs/SWC-116) | Check the 15-second miner variance window mentioned in root cause against SWC-116 specs. |
| 9 | `swc-115` | Authorization through tx.origin | [SWC-115 Docs](https://swcregistry.io/docs/SWC-115) | Verify that phishing call chain explanations accurately differentiate `tx.origin` from `msg.sender`. |
| 10 | `swc-105` | Unprotected Ether Withdrawal | [SWC-105 Docs](https://swcregistry.io/docs/SWC-105) | Confirm missing modifier explanations match unprotected ether withdrawal examples in SWC. |
| 11 | `swc-110` | Assert Violation | [SWC-110 Docs](https://swcregistry.io/docs/SWC-110) | Check the distinction between `require()` (input/precondition) and `assert()` (invariants). |
| 12 | `swc-114` | Transaction Order Dependence | [SWC-114 Docs](https://swcregistry.io/docs/SWC-114) | Check the front-running and slippage/deadline remediation advice against SWC recommendations. |

---

## 6. Feedback Message for Developer

You can copy and send the following message directly to Angel:

```markdown
Hi Angel,

Thank you for your work on Milestone M4! The foundation you built for corpus ingestion—specifically the five-level chunking logic (taxonomy, incident, root_cause, exploit_pattern, remediation), fastembed dense+sparse dual embeddings, and content-hash idempotency—is well designed and mathematically clean. Your summaries in the seed files are also high-quality original writing that clearly avoided verbatim copying.

However, after running our verification suite, the branch cannot be merged yet because several core deliverables of the M4 workstream are missing or incomplete. Here is the priority list of what needs to be addressed:

1. [Priority 1 - Blocker] Grounding Verifier: Implement `verify_draft(draft, chunks, model, manifest) -> FindingDraft | None` in `packages/auditor_core/auditor_core/verifier/` enforcing the 10 deterministic rules (exact quote checking, chunk resolution, span checks, severity clamps, prompt injection stripping, and routing unverified claims to unscored observations).
2. [Priority 1 - Blocker] Real Retrieval Engine: Replace `fake_retrieve.py` with `retrieve_evidence(candidate: CandidateSummary) -> RetrievalResult` in `packages/auditor_core/auditor_core/rag/retrieval.py` implementing live Qdrant hybrid search (dense + BM25 RRF fusion), vuln_class filtering, parent-child expansion, score thresholding (>= 0.35), and graceful fail-soft.
3. [Priority 1 - Blocker] Slither Detector Map: Create `packages/auditor_core/auditor_core/rag/detector_map.yaml` mapping all 15 curated Slither detectors to agreed vulnerability classes and SWC IDs.
4. [Priority 1 - Blocker] Retrieval Evaluation Suite: Add `eval/retrieval/golden_set.yaml` with 100+ labeled query pairs (including negatives) and a runner script measuring recall@5 (target >= 0.85).
5. [Priority 2 - Major] Monorepo Integration: Relocate everything from `defi/` into the proper monorepo paths (`packages/auditor_core/auditor_core/rag/`, `corpus/seed/`, and `eval/retrieval/`) and remove the `defi/` directory.
6. [Priority 2 - Major] Corpus Expansion & Taxonomy: Expand the corpus to the target minimums (35+ SWC entries and ~100 incident postmortems) and align the `vuln_class` tags with the agreed 10 classes in `severity_defaults.yaml`.
7. [Priority 2 - Major] Ingestion Enhancements: Wire database mirroring to the `corpus_documents` table and compute/stamp `corpus_version`.
8. [Priority 3 - Hygiene]: Remove committed SQLite binaries (`storage.sqlite`), lock files, and build artifacts from git; add them to `.gitignore`; and clean up the 8 ruff lint warnings and personal path references.

Please let me know if you have any questions about the interface contracts or test harnesses!
```

---

## 7. Commands Executed to Reproduce Results

To independently verify these findings, run the following commands from the repository root:

```bash
# 1. Inspect commit changes and files
git log -n 5 --stat origin/angel-m4
git diff main...origin/angel-m4 --stat

# 2. Run Ruff Lint on submitted code
.venv/bin/ruff check defi/

# 3. Run developer's ingestion unit tests
PYTHONPATH=defi/packages .venv/bin/python3 -m pytest defi/tests/test_ingest.py

# 4. Test Ingestion CLI dry run
PYTHONPATH=defi/packages .venv/bin/python3 -m auditor.corpus ingest defi/corpus/seed --dry-run

# 5. Run Corpus Audit (validates schema, URLs, duplication, and live source matches)
.venv/bin/python3 tests/verification/audit_corpus.py

# 6. Run Retrieval Behavior & Query Benchmark
PYTHONPATH=.:defi .venv/bin/python3 tests/verification/test_retrieval_behavior.py

# 7. Run Verifier Adversarial Suite
PYTHONPATH=. .venv/bin/python3 tests/verification/test_verifier_adversarial.py
```


# Developer Console Notes & Reference

## 1. Overview
The Test Console (`tester frontend`) is an internal test and verification harness built with Next.js and TypeScript. Its sole purpose is to exercise, debug, and inspect backend capabilities while the backend is implemented in parallel.

---

## 2. Screens Built

1. **API Catalog & Live Status (`/`)**:
   - Lists every documented route in the backend with real-time status indicators (OK, NOT IMPLEMENTED YET, ERROR, UNTESTED) and latency measurements.
   - Embeds interactive OpenAPI specification schema viewer.

2. **Health & Identity (`/health`)**:
   - `GET /health` (public status and version).
   - `GET /me` (authenticated current user, organization ID, and configured rate/upload limits).

3. **API Keys (`/api-keys`)**:
   - `POST /api-keys`: Creates new scoped API keys and displays the raw `ak_live_...` key once.
   - `GET /api-keys`: Lists active/revoked API keys.
   - `DELETE /api-keys/{id}`: Soft revocation.
   - Built-in Negative Test: Retries calls with the revoked key to confirm HTTP 401 rejection.

4. **Projects (`/projects`)**:
   - `POST /projects`: Scaffolds projects.
   - `GET /projects`: Lists multi-tenant scoped projects.
   - `GET /projects/{id}`: Inspects project metadata.
   - `DELETE /projects/{id}`: Soft deletion and audit purge trigger.

5. **Uploads (`/uploads`)**:
   - `POST /uploads`: Uploads Solidity contracts (`.sol`) or archives (`.zip`).
   - Displays computed SHA256 checksums, byte counts, and expiration timestamps.
   - Built-in Negative Tests:
     - Path-traversal zip attack (`../../evil.sol`) asserting HTTP 422 rejection.
     - Oversized file upload (>10MB payload) asserting HTTP 413 rejection.

6. **Audits (`/audits`)**:
   - `POST /projects/{id}/audits`: Creates an audit job with customizable options (solc version, feature toggles, retention hours) and initial role declarations.
   - `GET /audits`: Lists audits with multi-parameter filtering.
   - `GET /audits/{id}`: Deep inspects status, compiler version, coverage statement, scores, and errors.
   - `POST /audits/{id}/cancel`: Halts ongoing audit execution.
   - `DELETE /audits/{id}`: Triggers immediate object-store purge.

7. **Live Progress SSE Stream (`/events`)**:
   - Real-time Server-Sent Events (SSE) from `/v1/audits/{id}/events`.
   - Reconnect support with `Last-Event-ID` tracking.
   - Polling fallback toggle switch (2.5s interval).

8. **Files & Code Viewer (`/files`)**:
   - `GET /audits/{id}/files`: Lists uploaded source manifest files and dependencies.
   - `GET /audits/{id}/files/{fid}`: Plain-text code viewer with line numbers and character coordinate tracking.

9. **Privilege Map (`/privilege-map`) [Flagship]**:
   - `GET /audits/{id}/privilege-map`: Full roles table (blast score, tier, worst-case scenario, assumed vs declared badge).
   - Drilldown functions list with line span jump links.
   - Undetected notes section ("What this view cannot see").
   - `PUT /audits/{id}/role-declarations`: Interactive role-holder declaration form (multisig, timelock, EOA, renounced) computing before/after score diffs in real time.

10. **Findings & Evidence (`/findings`)**:
    - `GET /audits/{id}/findings`: Findings filtered by severity, source, and open/dismissed status.
    - `GET /audits/{id}/findings/{fid}`: Detail view with line spans and evidence cards (kind, title, locator, exact quote, retrieval score).
    - `PATCH /audits/{id}/findings/{fid}`: Toggles finding dismissal.
    - Unverified LLM hypotheses drawer.

11. **Automated Patches (`/patches`)**:
    - `POST /audits/{id}/findings/{fid}/patches`: Generates code fixes for specific findings.
    - Color-coded red/green unified diff viewer.
    - Status badges (compiles, finding cleared, tests passed).
    - Edit-and-reverify diff box submitting custom diffs for automated reverification.

12. **Proofs & Invariants (`/proofs`)**:
    - `GET /audits/{id}/proofs`: Exploit test source and Foundry run log inspector.
    - `GET /audits/{id}/invariants`: Invariant run results and counterexamples with feature-flag notices.

13. **Exports (`/exports`)**:
    - `GET /audits/{id}/export?format=...`: One-click exports in JSON, Markdown, SARIF, and PDF format.
    - File size display, direct browser file download, and 40-line text preview.

14. **Security Corpus (`/corpus`)**:
    - `GET /corpus/versions`: Displays available security incident dataset versions and document counts.

15. **Automated Verification Suite (`/checks`)**:
    - "Run All Checks" executes the 10-point end-to-end verification suite against the live backend and reports PASS / FAIL / SKIPPED.

---

## 3. Endpoints Covered vs OpenAPI Mismatches

| Endpoint | Documentation (`api_endpoints.md`) | OpenAPI Implementation (`services/api`) | Notes |
|---|---|---|---|
| `GET /health` | Unauthenticated probe | `/v1/health` | Verified |
| `GET /me` | Identity & limits | `/v1/me` | Uses dev tokens in local mode |
| `POST /uploads` | Multipart `.sol` or `.zip` | `/v1/uploads` | Enforces zip safety & size |
| `POST /projects/{id}/audits` | Queued audit job | `/v1/projects/{id}/audits` | Supports local asyncio worker or Arq/Redis |
| `GET /audits/{id}/events` | SSE text/event-stream | `/v1/audits/{id}/events` | SSE streaming supported |
| `GET /audits/{id}/privilege-map` | Privilege graph & table | `/v1/audits/{id}/privilege-map` | Flagship Milestone 2 |
| `PUT /audits/{id}/role-declarations` | Sync recompute | `/v1/audits/{id}/role-declarations` | Recalculates blast scores |
| `GET /audits/{id}/export` | Reports | `/v1/audits/{id}/export` | Supports json, md, sarif, pdf |
| `GET /corpus/versions` | Dataset versions | `/v1/corpus/versions` | Seed corpus versioning |

---

## 4. How to Add a New Screen

1. **Add Route Page**: Create a new file under `tester frontend/src/app/<feature>/page.tsx`.
2. **Import Unified Client**:
   ```typescript
   import { executeApiRequest } from "@/lib/api";
   import { useConsole } from "@/lib/store";
   import { ErrorDisplay } from "@/components/ErrorDisplay";
   import { RawJsonViewer } from "@/components/RawJsonViewer";
   ```
3. **Execute API Calls**:
   ```typescript
   const { authMode, apiKey, addLogEntry } = useConsole();
   const res = await executeApiRequest("/your-endpoint", {
     method: "GET",
     authMode,
     apiKey,
     onLog: addLogEntry,
   });
   ```
4. **Register in Left Nav**: Open `tester frontend/src/components/Layout.tsx` and add an entry to `NAV_ITEMS`:
   ```typescript
   { href: "/your-feature", label: "Feature Name" }
   ```
5. **Update Types**: If backend schemas change, run:
   ```bash
   make gen-console-types
   ```


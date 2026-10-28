# Frontend Architecture

Next.js (App Router), TypeScript strict, Tailwind, shadcn/ui, TanStack Query, Zustand, Monaco, React Flow. Dark theme by default (see `ui_design_system.md`).

## 1. Routes

| Route | Purpose | Notes |
|---|---|---|
| `/login` | OIDC sign-in | public |
| `/` | redirect to `/projects` | |
| `/projects` | Project list + create | |
| `/projects/[projectId]` | Audits for a project, "New audit" | |
| `/projects/[projectId]/audits/new` | Upload + options + optional role declarations | |
| `/audits/[auditId]` | **Audit workspace** (default tab: Overview) | live progress while running |
| `/audits/[auditId]/privilege-map` | Privilege Map graph + holder declarations | flagship screen |
| `/audits/[auditId]/findings` | Findings list + filters | |
| `/audits/[auditId]/findings/[findingId]` | Finding detail: code, evidence, patch, proof | |
| `/audits/[auditId]/invariants` | Invariant results (M7) | feature-flagged |
| `/audits/[auditId]/report` | Coverage statement, scoring, exports | |
| `/settings/api-keys` | Manage API keys | |
| `/api/proxy/[...path]` | Backend proxy route (server) | attaches token |

Audit workspace uses a shared layout `audits/[auditId]/layout.tsx` with a left file tree, a top tab bar (Overview, Privilege Map, Findings, Invariants, Report) and a persistent disclaimer footer.

## 2. Directory Structure

```
apps/web/src
├─ app/                       # routes (above)
├─ components/
│  ├─ ui/                     # shadcn primitives
│  ├─ layout/                 # AppShell, TopBar, DisclaimerBanner
│  ├─ audit/                  # ProgressPanel, CoverageCard, ScoreBadge
│  ├─ code/                   # CodeViewer, FileTree, SpanHighlighter
│  ├─ privilege/              # PrivilegeGraph, RoleNode, PowerNode, RoleDrawer,
│  │                          # HolderDeclarationForm, ScoreBreakdown, WorstCaseCard
│  ├─ findings/               # FindingList, FindingFilters, FindingCard, SeverityPill,
│  │                          # EvidenceCard, EvidenceDrawer
│  ├─ patch/                  # DiffViewer, PatchStatusBadges, EditAndReverify
│  └─ upload/                 # Dropzone, SourceSummary
├─ hooks/                     # useAuditEvents, useDebounce, useSpanNavigation
├─ lib/
│  ├─ api/                    # client.ts, schema.d.ts (generated), queries.ts
│  ├─ auth/                   # session helpers
│  └─ format.ts, disclaimer.ts
├─ stores/                    # zustand: useEventLog, useWorkspaceUI
└─ styles/
```

## 3. State Management

| State | Where | Examples |
|---|---|---|
| Server data | TanStack Query | audits, privilege map, findings, patches |
| Live events | Zustand `useEventLog` | progress log lines for the current audit |
| Workspace UI | Zustand `useWorkspaceUI` | selected file, highlighted span, open drawer, graph filters |
| Forms | React Hook Form + zod | upload options, holder declarations |
| URL state | `searchParams` | findings filters (`?severity=high&source=slither`), selected role (`?role=OWNER`) |

Rules: no server data copied into Zustand; selection that should be shareable goes in the URL; mutations update the Query cache from the response.

## 4. Key Screens

### 4.1 New Audit
Dropzone for `.sol`/`.zip` (summary of detected files after upload), options (solc version auto/override, feature toggles with only available milestones enabled), collapsible "Declare who holds each role (optional)" section, notice about retention (default 24 h) and privacy. Submit shows progress via SSE.

### 4.2 Audit Overview
- Progress stepper bound to `stage` while running; log panel from `useEventLog`.
- On complete: score badge labeled **"Heuristic risk indicator"**, severity counts, top 3 privilege risks, **Coverage card** (analyzed / not analyzed / out of scope), disclaimer.
- Failed builds show diagnostics list.

### 4.3 Privilege Map (flagship)
Layout: graph (left, ~65%), detail drawer (right).

Graph (React Flow):
- **Role nodes** in the left column; **power nodes** (one per privileged function, grouped by category) in the right column. Edges: `can_call` (solid) and `can_grant` (dashed, role to role).
- Node color by tier (none gray, low blue, medium amber, high orange, critical red) plus an icon/shape so color is not the only signal.
- Role node shows `blast_score`, tier, and holder badge: `Single key (assumed)` in warning style when `holder_assumed`.
- Clicking a role opens `RoleDrawer`: worst-case sentence, mitigations list (cap, delay, two-step, reversible, each with a check or cross), actions table (function, span link, category, score), score breakdown ("How is this scored?"), and `HolderDeclarationForm`.
- Clicking a power node jumps the code viewer to the function span.
- Filters: tier, category, "only unmitigated".
- Toggle: graph / table view (table is the accessible and mobile-friendly default on narrow screens).
- Changing a holder declaration calls the mutation with 400 ms debounce, updates scores in place with a brief highlight on changed values.
- Footer note lists `undetected_notes` ("What this view cannot see").

### 4.4 Findings
List with severity pill, title, location, source badge (`Static`, `Privilege`, `Invariant`, `Proven`), filters, and a separate collapsed "Unverified observations" section (visually distinct, unscored). Detail page: side-by-side layout, left Monaco with highlighted spans, right tabs: **Summary**, **Evidence**, **Patch**, **Proof**. Evidence cards show the exact quote, source link and relevance; static_fact cards show detector and facts. If no precedent was retrieved, show that explicitly.

### 4.5 Patch Review
`DiffViewer` side-by-side red/green diff; badges for `Compiles`, `Finding cleared`, `No new findings`, `Tests`, `Gas (+/-)` (or "not measured"). Actions: Copy diff, Download patch, Edit and re-verify (opens editable diff, calls `POST /patches/{id}/verify`), Reject. Never offer "Apply" to a patch whose status is not `verified`.

### 4.6 Report
Coverage statement, scoring weights, toolchain and corpus versions, export buttons (JSON / MD / SARIF / PDF), and the full disclaimer.

## 5. Components: Contracts

```ts
type CodeViewerProps = { auditId: string; fileId: string; highlights: Span[]; onSpanClick?: (s: Span) => void };
type PrivilegeGraphProps = { map: PrivilegeMap; selectedRole?: string; filters: GraphFilters; onSelectRole(k: string): void; onSelectAction(id: string): void };
type HolderDeclarationFormProps = { roleKey: string; value?: RoleHolderDeclaration; onChange(v: RoleHolderDeclaration | null): void };
type EvidenceCardProps = { evidence: Evidence };
type DiffViewerProps = { unifiedDiff: string; editable?: boolean; onChange?(diff: string): void };
```

## 6. Performance and Robustness

- Monaco and React Flow loaded with `dynamic(..., { ssr: false })`.
- Virtualize findings list over 200 items.
- File content fetched on demand and cached (`staleTime: Infinity`, audits are immutable once complete).
- Graph layout computed once per map version (memoize on `scoring_config_version + roles hash`); cap rendered power nodes at about 150 and group the rest ("+23 more in Admin Settings").
- All screens have loading skeletons, empty states, and error states with `request_id`.

## 7. Accessibility and Content Rules

- WCAG AA contrast; full keyboard navigation of graph nodes (Tab/Enter) and a table alternative.
- Severity conveyed by text + icon + color.
- Persistent `DisclaimerBanner`; never display wording like "safe", "secure", or "compliant" as a verdict. Use: "No verified issues detected by this analysis."
- Reports and screens always show the coverage statement.

## 8. Testing (frontend)

- Component tests (Vitest + Testing Library) for `HolderDeclarationForm` validation, `EvidenceCard`, `DiffViewer`.
- Playwright E2E: upload fixture, wait for completion, assert Privilege Map roles/tiers, change holder to 3-of-5 multisig and assert score drops, open a finding and see evidence, dismiss a finding.
- Visual regression on the graph for 3 fixtures.

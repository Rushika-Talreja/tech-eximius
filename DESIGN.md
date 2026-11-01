---
name: Warm Obsidian Security Engine
colors:
  surface: '#161311'
  surface-dim: '#161311'
  surface-bright: '#3d3836'
  surface-container-lowest: '#100e0c'
  surface-container-low: '#1e1b19'
  surface-container: '#221f1d'
  surface-container-high: '#2d2927'
  surface-container-highest: '#383431'
  on-surface: '#e9e1dd'
  on-surface-variant: '#d5c4af'
  inverse-surface: '#e9e1dd'
  inverse-on-surface: '#34302d'
  outline: '#9d8e7c'
  outline-variant: '#514535'
  surface-tint: '#feba49'
  primary: '#ffbb49'
  on-primary: '#442c00'
  primary-container: '#e0a030'
  on-primary-container: '#583a00'
  inverse-primary: '#805600'
  secondary: '#d0c5b9'
  on-secondary: '#362f27'
  secondary-container: '#4d463d'
  on-secondary-container: '#beb3a8'
  tertiary: '#9accff'
  on-tertiary: '#003354'
  tertiary-container: '#65b2f6'
  on-tertiary-container: '#00436c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffddb0'
  primary-fixed-dim: '#feba49'
  on-primary-fixed: '#281800'
  on-primary-fixed-variant: '#614000'
  secondary-fixed: '#ece1d4'
  secondary-fixed-dim: '#d0c5b9'
  on-secondary-fixed: '#201b13'
  on-secondary-fixed-variant: '#4d463d'
  tertiary-fixed: '#cee5ff'
  tertiary-fixed-dim: '#98cbff'
  on-tertiary-fixed: '#001d33'
  on-tertiary-fixed-variant: '#004a77'
  background: '#161311'
  on-background: '#e9e1dd'
  surface-variant: '#383431'
typography:
  display:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  display-mobile:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.01em
  code-lg:
    fontFamily: JetBrains Mono
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.08em
  disclaimer:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.03em
spacing:
  gutter: 1.5rem
  gutter-mobile: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system delivers an austere, rigorous, and highly legible terminal-inspired interface engineered specifically for Solidity smart contract security evaluation. The aesthetic fuses technical brutalism with warm industrial ergonomics, rejecting frivolous visual clutter to focus entirely on code integrity and vulnerability telemetry.

The target audience comprises smart contract engineers, protocol founders, and security researchers seeking immediate, unbiased vulnerability pre-assessments before undergoing human audits. The interface evokes unyielding objectivity, calm technical confidence, and disciplined transparency. 

Key architectural guardrails:
- **Strict Text-First UI**: Eliminate all abstract icons, symbolic glyphs, arrows, chevrons, checkmarks, bullets, plus/minus indicators, and status dots. All interactive affordances, states, and navigations are executed through explicit text labels (e.g., "Expand", "Collapse", "Complete", "Active", "Added", "Removed", "Open", "Dismiss").
- **Zero Cold Hues**: Completely eliminate all blues, purples, cyans, teals, lavenders, and cool-cast grays. Every operational surface, interaction highlight, focus boundary, and link leans strictly into an amber and warm charcoal spectrum.
- **Persistent Regulatory Context**: Every root surface, export document, and terminal view carries the immutable security posture disclaimer: `"Automated advisory check. Not a formal audit. Not legal advice."`

## Colors

The color palette operates strictly in a warm dark spectrum. Surfaces are anchored by deep charcoal with earthy brown undertones, ensuring high contrast against text while eliminating screen fatigue during extensive code review sessions.

### Application Palette

- **Base Background (`#14110F`)**: Canvas foundation for root viewports and non-interactive gutter planes.
- **Surface (`#1D1916`)**: Primary plane for code modules, audit parameter cards, and data matrices.
- **Raised Surface (`#26211D`)**: Floating diagnostic panels, popovers, contextual tooltips, and elevated table headers.
- **Structural Border (`#3A332D`)**: 1px separation boundaries across cards, tabs, and code line gutters.
- **Text Primary (`#F2EBE3`)**: Unadulterated warm off-white for code tokens, primary metrics, and headers.
- **Text Secondary (`#A89E93`)**: Calibrated warm neutral for metadata, line numbers, and helper descriptions.
- **Brand Accent & Action (`#E0A030`)**: Pure amber. Sole driver for primary buttons, focus rings, progress tracks, active tab indicators, and textual hyperlink anchors.

### Severity & Diff System

Color is strictly reserved for diagnostic meaning:
- **Critical (`#D6403A`)**: Re-entrancy vulnerabilities, logic bugs causing direct drain of funds, self-destruct vectors.
- **High (`#E8782A`)**: Access-control deviations, unchecked return values, oracle manipulation surfaces.
- **Medium (`#E3B73C`)**: Front-running vectors, gas griefing risks, state-reordering hazards.
- **Low (`#8FA84A`)**: Floating pragmas, dead code, style divergence, sub-optimal assembly efficiency.
- **Patch Added (`#4C9A5B`)**: Recommended secure line injection.
- **Patch Removed (`#C4453F`)**: Identified vulnerable line removal.

Under no circumstances may any component introduce blue, cyan, purple, or cool-slate tokens.

## Typography

The typographic hierarchy enforces high legibility through dual typefaces: **Inter** for operational prose, form headers, and system communication, and **JetBrains Mono** for contract logic, AST diagnostics, bytecode traces, diff outputs, and telemetry tags.

### Rules of Usage
- **JetBrains Mono** governs all data density, line counts, severity badges, patch snippets, and interactive metadata tags. It is rendered with crisp subpixel anti-aliasing.
- **Inter** is reserved for macro-level structural navigation, advisory summaries, and vulnerability explanations.
- All labels and status readouts using `label-caps` must be authored in full uppercase (e.g., `CRITICAL`, `RUN AUDIT`, `PATCH APPLIED`, `EXPAND DIFF`).
- The persistent advisory disclaimer must strictly use the `disclaimer` token in secondary text (`#A89E93`) to maintain presence without competing with findings.

## Layout & Spacing

The layout employs a high-density, mathematical 12-column grid system tuned for asymmetric multi-pane views (e.g., File Tree / AST View / Vulnerability Inspector / Code Workspace).

### Breakpoints & Adaptations
- **Desktop (1280px and above)**: Full 12-column layout. 2rem outer margins, 1.5rem gutters. Supports a three-column IDE split: File & Contract Navigation (3 columns), Interactive Solidity Diff View (6 columns), Findings & Mitigation Matrix (3 columns).
- **Tablet (768px – 1279px)**: 8-column layout. 1.5rem margins, 1rem gutters. Contract view and Diagnostic inspector reflow into vertically stacked panels with sticky navigation toggles.
- **Mobile (Below 768px)**: 4-column layout. 1rem margins, 0.75rem gutters. Interface reflows strictly into a linear vertical feed. Actions lock into full-width tap targets with text-first labels.

All internal component paddings strictly increment on the 4px baseline (`space-xs` = 4px, `space-sm` = 8px, `space-md` = 16px, `space-lg` = 24px, `space-xl` = 40px). Dense code panels rely exclusively on `space-xs` and `space-sm` to maximize vertical line visibility.

## Elevation & Depth

This design system rejects deep blur filters, colored drop shadows, and skeuomorphic gradients in favor of **structural low-contrast outlines** and **monolithic tonal surfaces**. Depth is communicated through calibrated luminance steps:

- **Level 0 (Canvas Base `#14110F`)**: Canvas ground plane and static editor gutter tracks.
- **Level 1 (Card & Module Layer `#1D1916`)**: Default containers, finding summaries, and diff workspaces. Outlined by a continuous 1px solid border (`#3A332D`).
- **Level 2 (Raised & Interactive `#26211D`)**: Hovered code blocks, active selection rows, parameter flyouts, modal drawers. Outlined by a 1px solid border (`#3A332D`), elevated cleanly without shadows.
- **Level 3 (Focused State)**: When an element or row receives system focus, elevate via a 1px sharp amber border (`#E0A030`) and a subtle 0 0 0 1px `#E0A030` outline ring. No soft blur diffusion.

Diff additions and removals apply low-luminance tinted backgrounds beneath code lines:
- Additions: `#4C9A5B` at 12% opacity over `#1D1916` with a solid 2px left border in `#4C9A5B`.
- Deletions: `#C4453F` at 12% opacity over `#1D1916` with a solid 2px left border in `#C4453F`.

## Shapes

The geometric framework is entirely **Sharp (`0px` border radius)** across all UI elements, inputs, containers, badges, dialogs, and code blocks.

### Geometric Philosophy
- Curves, rounded corners, pill shapes, and soft radiuses are prohibited. 
- The 90-degree orthogonal edge reinforces the rigorous, terminal-inspired identity of smart contract auditing, echoing the strict, unyielding nature of EVM execution and bytecode compilation.
- Badges, buttons, diff containers, tables, and dropdowns share unrounded, razor-sharp perimeters bounded by 1px solid hairline borders.

## Components

All components adhere strictly to the no-glyph, text-only paradigm and the warm charcoal/amber color palette.

### Buttons & Interactive Controls
- **Primary Action**: Amber background (`#E0A030`), deep charcoal text (`#14110F`), `label-caps` font, sharp corners, padding `space-sm` `space-lg`. Text reads explicitly: `"Run Audit"`, `"Accept Patch"`, `"Export Report"`. On hover: `#F2B850`. On active: `#C88C24`. On focus: 2px offset border in `#E0A030`.
- **Secondary Action**: Transparent background, 1px solid border (`#3A332D`), primary text (`#F2EBE3`). On hover: background `#26211D`, border `#E0A030`. Text reads: `"View Source"`, `"Analyze Trace"`, `"Cancel"`.
- **Destructive Action**: Transparent background, 1px solid border (`#D6403A`), text `#D6403A`. On hover: background `#D6403A` at 15% opacity. Text reads: `"Revoke Approval"`, `"Dismiss Finding"`.

### Severity Indicators & Status Labels
- Rendered as sharp rectangular badges with 1px borders and uppercase monospace text (`label-caps`).
- **Critical**: Border `#D6403A`, text `#D6403A`, background `#D6403A` at 10% opacity. Label reads: `"CRITICAL"`.
- **High**: Border `#E8782A`, text `#E8782A`, background `#E8782A` at 10% opacity. Label reads: `"HIGH"`.
- **Medium**: Border `#E3B73C`, text `#E3B73C`, background `#E3B73C` at 10% opacity. Label reads: `"MEDIUM"`.
- **Low**: Border `#8FA84A`, text `#8FA84A`, background `#8FA84A` at 10% opacity. Label reads: `"LOW"`.
- Never use colored circles, warning icons, or alert shields. The severity name is the indicator.

### Disclosure Toggles & Navigation
- Replaces chevrons and expand arrows with explicit binary text:
  - Collapsed state: Button reading `"Show Details"`, `"Expand Diff"`, or `"Show Trace"`.
  - Expanded state: Button reading `"Hide Details"`, `"Collapse Diff"`, or `"Hide Trace"`.
- Pagination and step sequences use `"Previous"` and `"Next"` textual actions, paired with `"Step 1 of 4"`.

### Selection Controls (Checkboxes & Radios)
- **Checkboxes**: Sharp square frame (16px x 16px) with 1px border `#3A332D`. Unchecked displays an empty frame. Checked displays a solid amber (`#E0A030`) background filled with the centered text label `"YES"` or `"ON"` in 9px JetBrains Mono bold charcoal (`#14110F`). Alternatively, text toggles reading `"[ Selected ]"` and `"[ Unselected ]"` may be utilized for inline lists.
- **Radio Buttons**: Rectangular segmented chips. Selected option: background `#26211D`, border `#E0A030`, text `#E0A030`. Unselected option: border `#3A332D`, text `#A89E93`.

### Input Fields & Code Upload Zones
- Single-line and multi-line inputs: Background `#1D1916`, 1px border `#3A332D`, text `#F2EBE3`, font `code-md`.
- Placeholder text: `#A89E93` at 60% opacity.
- Focus state: Border transitions to `#E0A030`, with no soft shadow glow.
- Upload/Drop zones: 1px dashed border `#3A332D`, background `#1D1916`. Action reads: `"Select Solidity File (.sol) or Paste Contract Code"`.

### Findings Cards & Audit Matrix
- Enclosed in a 1px border `#3A332D` over `#1D1916`.
- Card Header: Monospace finding ID (`#A89E93`, e.g., `"FINDING-082"`), contract method name (`#F2EBE3`), and severity badge aligned right.
- Card Body: Inter `body-md` for vulnerability explanation and vector analysis.
- Remediation Block: Split-view or unified diff container. Removed code is prefixed with the textual tag `"REMOVED"` and tinted with `#C4453F`; added code is prefixed with `"ADDED"` and tinted with `#4C9A5B`.
- Card Footer: Persistent inline micro-label: `"Automated advisory check. Not a formal audit. Not legal advice."`


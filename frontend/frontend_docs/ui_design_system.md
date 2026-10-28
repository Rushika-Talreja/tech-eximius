# UI Design System

Goal: a calm, dark, low-cognitive-load interface for security work. Information first, alarm only when warranted.

## 1. Principles

1. **Summary first, detail on demand.** Every screen leads with the answer, with drill-down underneath.
2. **One primary action per card.**
3. **Alarm is earned.** Red is reserved for confirmed critical/high items. Uncertainty is shown with neutral/amber styling and explicit labels ("assumed", "unverified").
4. **Never color alone.** Pair color with icon and text.
5. **Show the evidence.** Claims always have a visible path to their source.
6. **Honest limits.** Coverage and disclaimer are always reachable.

## 2. Tokens (CSS variables, dark default; light optional later)

```css
:root {
  --bg:            #0B0F14;
  --surface:       #121821;
  --surface-2:     #18202B;
  --border:        #243040;
  --text:          #E6EDF3;
  --text-muted:    #9AA7B5;
  --accent:        #5B9DFF;

  --sev-critical:  #FF5C6C;
  --sev-high:      #FF8A4C;
  --sev-medium:    #F5C451;
  --sev-low:       #5BB5FF;
  --sev-info:      #8B98A8;
  --ok:            #4CC38A;
  --warn-assumed:  #E0B341;   /* "assumed" / unverified labels */

  --diff-add-bg:   rgba(76,195,138,.14);  --diff-add-fg: #7EE0AE;
  --diff-del-bg:   rgba(255,92,108,.14);  --diff-del-fg: #FF9AA5;

  --radius: 10px;
  --font-sans: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}
```
All text/background pairs must meet WCAG AA (4.5:1 body, 3:1 large). Verify with an automated contrast test on tokens.

## 3. Typography and Spacing

- Base 14px UI, 13px code. Headings 20/16/14 semi-bold. Line height 1.5.
- 4px spacing scale (4, 8, 12, 16, 24, 32). Cards use 16 to 24px padding.

## 4. Core Components

| Component | Spec |
|---|---|
| `SeverityPill` | icon + label + token color; shapes differ by level (e.g. filled diamond critical, circle info) |
| `TierBadge` | privilege tier, same palette as severity, with numeric score |
| `AssumedBadge` | outlined `--warn-assumed`, text "Assumed: single key" with tooltip explaining how to declare |
| `EvidenceCard` | source icon, title, locator, exact quote in blockquote (mono 13px), "Open source" link, relevance meter |
| `CoverageCard` | three columns: Analyzed, Not analyzed, Out of scope, always expandable |
| `DisclaimerBanner` | slim, persistent footer, expandable full text |
| `DiffViewer` | side-by-side, add/del tokens above, line numbers, gutter badges; unified toggle |
| `StatusBadges` (patch) | Compiles, Cleared, No new findings, Tests, Gas |
| `ProgressStepper` | stage list with spinner / check / x, elapsed time per stage |
| `EmptyState` | icon, one-line explanation, one action |

## 5. Graph Styling (Privilege Map)

- Canvas `--bg`, nodes `--surface-2` with 2px tier-colored left border; critical nodes get a subtle glow, not animation.
- Edges: `can_call` 1.5px `--text-muted`; `can_grant` dashed `--accent`.
- Selected node: 2px `--accent` outline. Hover: show tooltip with worst-case sentence.
- Reduced motion respected (`prefers-reduced-motion`): no animated edges or glow transitions.

## 6. Copy Guidelines

- Use: "No verified issues detected by this analysis", "Heuristic risk indicator", "Assumed single key", "Not analyzed".
- Avoid: "safe", "secure", "compliant", "certified", "guaranteed", "audit passed".
- Findings: state what, where, why it matters, how to fix, in that order, max about 60 words in the summary.
- Standard disclaimer text lives in one constant (`lib/disclaimer.ts`) and is the same on screen, API, and exports.

## 7. Responsive Behavior

- Desktop: three-pane workspace (files / code / findings or graph / drawer).
- Tablet: two-pane with collapsible file tree.
- Mobile: single column; Privilege Map defaults to table view; diffs switch to unified.

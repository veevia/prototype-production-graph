---
doc: design
status: filled
project: Lot Release Workbench (fictional example)
---

# Design — Lot Release Workbench (fictional example)

> **TL;DR:** Calm, dense and tabular: the numbers lead, status is icon + text + colour, and red means a failure.

## Visual language

Quiet neutrals, one accent for actions, status colours only for status. Tables for comparison and audit.

## Layout

Queue: one table. Lot review: the comparison table leads; the derived verdict opens the decision panel beside it (≥ 1024 px) or after it — evidence, then verdict, then decision.

## Typography

| Token | Size (px) | Weight | Line height | Use |
|---|---|---|---|---|
| xs | 12 | 600 | 1.4 | — |
| sm | 14 | 400 | 1.5 | — |
| md | 16 | 400 | 1.5 | — |
| lg | 18 | 600 | 1.35 | — |
| xl | 20 | 600 | 1.3 | — |
| 2xl | 24 | 600 | 1.25 | — |

## Color

| Token | Value | Role | Provenance |
|---|---|---|---|
| color-canvas | #F6F7F9 | page canvas | Fabrikam Quality UI guide (S-07) |
| color-surface | #FFFFFF | panels and tables | Fabrikam Quality UI guide (S-07) |
| color-surface-alt | #EEF0F3 | table headers, quiet surfaces | derived: 4% ink on canvas |
| color-border | #CDD2D9 | dividers | derived from ink |
| color-border-strong | #8A93A0 | control borders (≥ 3:1) | derived from ink |
| color-text | #1B1F24 | ink | Fabrikam Quality UI guide (S-07) |
| color-text-secondary | #4A5361 | secondary text | derived: ink 75% |
| color-text-subtle | #6B7280 | captions on white only | derived: ink 60% |
| color-accent | #0B5CAD | actions and links | Fabrikam Quality UI guide (S-07) |
| color-accent-strong | #084A8C | hover | derived: accent −15% |
| color-accent-tint | #E7F0FA | information banners | derived: accent 10% |
| color-on-accent | #FFFFFF | text on accent | Fabrikam Quality UI guide (S-07) |
| color-success | #1D6B37 | pass: text and icons | Fabrikam Quality UI guide (S-07) |
| color-success-tint | #E7F4EC | pass: backgrounds | Fabrikam Quality UI guide (S-07) |
| color-warning | #7A4F00 | attention: text and icons | Fabrikam Quality UI guide (S-07) |
| color-warning-tint | #FFF3D6 | attention: backgrounds | Fabrikam Quality UI guide (S-07) |
| color-alert | #B3261E | alert: failures and holds only | Fabrikam Quality UI guide (S-07) |
| color-alert-tint | #FDECEB | alert backgrounds: failures and holds only | Fabrikam Quality UI guide (S-07) |
| color-focus | #0B5CAD | focus ring | Fabrikam Quality UI guide (S-07) |

**Declared pairs:** color-text on color-surface (body text); color-text on color-canvas (page text); color-text-secondary on color-surface (secondary text); color-text-secondary on color-surface-alt (table headers, status chips); color-text-secondary on color-success-tint (verdict rule text); color-text-secondary on color-alert-tint (verdict rule text); color-text-secondary on color-warning-tint (verdict rule text); color-text-subtle on color-surface (captions); color-accent on color-surface (links); color-on-accent on color-accent (primary buttons); color-success on color-success-tint (pass chips); color-warning on color-warning-tint (attention chips); color-alert on color-alert-tint (failure chips); color-alert on color-surface (error titles); color-text on color-accent-tint (banners); color-border-strong on color-surface (control borders); color-focus on color-surface (focus ring); color-focus on color-canvas (focus ring on canvas). Ratios are recomputed by `design_system:check`.

## Components

- **Button:** primary, secondary, quiet — states default, hover, focus, disabled
- **Filter chip:** pressed, unpressed — states default, focus
- **Status chip:** ready/within, attention, failure, neutral status — states default
- **Data table:** queue, comparison, log — states default, stacked (< 640 px)
- **Decision option:** release, hold, reject — states default, checked, focus, locked
- **Text area:** rationale, notice — states default, focus, invalid
- **State panel:** loading, empty, error, not needed — states default

## Motion

No animation; Transitions ≤ 0.1 s; Nothing moves under prefers-reduced-motion.

## Responsive behavior

Breakpoints 640 and 1024 px; tables restack as labelled rows below 640 px.

## Accessibility

WCAG 2.2 AA; 44 px touch targets on tablets; A visible 2 px focus ring; One h1 per screen; headings in order.

## Prohibited patterns

- Gradients
- Status by colour alone
- Alert red outside failures and holds
- Left-accent highlight borders
- Decorative cards for row-by-row comparison
- Web fonts or any network asset
- Text below 12 px

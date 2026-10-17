---
title: "Design Handoff — <feature>"
type: template
template-for: design-handoff
status: canonical
owner: Wei Wei
last-updated: 2026-04-21
loop-phase: design
source: Author artifact template; private programme examples omitted
tags: [type/template, type/handoff, purpose/execute, loop/design, status/canonical]
---

# Design Handoff — &lt;feature name&gt;

> **👥 For engineering partners**
>
> This is the bridge between "what to build" (PRD) and "how it looks and behaves" (this doc). Everything here is buildable — no ambiguity left for interpretation. If something is unclear, flag it before sprint planning, not during code review.

> **TL;DR:** &lt;One sentence — what's being handed off, at what fidelity, covering which user flow.&gt;

## Who reviews what

| Function | Review | Sign-off needed? |
|---|---|---|
| Engineering | Full document — this is for you | Yes — feasibility + estimation |
| QA | States (§3), Interactions (§4), Edge cases (§9) | Yes — test coverage |
| Accessibility | §7 Accessibility annotations | Yes — WCAG compliance |
| Design system | §5 Component mapping | Advisory — flag new components |
| PM | §2 Scope, §10 Open questions | Advisory — confirm scope matches PRD |
| Content / copy | §6 Content and copy | Yes — all copy final |

## 1. Metadata

| Field | Value |
|---|---|
| Feature | &lt;name&gt; |
| PRD link | &lt;link to `2-3-Design_PRD.md`&gt; |
| Design POV link | &lt;link to `2-1-Design_POV.md`&gt; |
| Figma / prototype link | &lt;link&gt; |
| Design lead | &lt;name&gt; |
| Engineering lead | &lt;name&gt; |
| Date | YYYY-MM-DD |
| Status | draft / review / approved |

## 2. Scope of this handoff

What user flow(s) this covers. Not the full feature — the specific slice being built.

- **Flow:** &lt;e.g., "Primary persona completes async review from notification to confirmation"&gt;
- **Not included in this handoff:** &lt;e.g., "Settings page, admin view, mobile breakpoint"&gt;

## 3. Screen and state inventory

List every screen or view, and every state each screen can be in. If it's not listed, engineering will assume it doesn't exist.

| # | Screen / view | States |
|---|---|---|
| 1 | &lt;e.g., Review inbox&gt; | default, empty, loading, error, 1 item, 10+ items |
| 2 | &lt;e.g., Review detail&gt; | read-only, editable, submitted, conflict |
| 3 | &lt;...&gt; | |

**Figma page mapping:** &lt;link to the specific Figma page/frame for each screen&gt;

## 4. Interaction specs

For each non-obvious interaction. Skip what the design system already handles.

### 4a. &lt;Interaction name — e.g., "Submit review"&gt;

- **Trigger:** &lt;what the user does&gt;
- **System response:** &lt;what happens, step by step&gt;
- **Loading state:** &lt;what the user sees while waiting&gt;
- **Success state:** &lt;what confirms completion&gt;
- **Error state:** &lt;what happens on failure + recovery path&gt;
- **Edge case:** &lt;e.g., "Double-click prevention", "Network timeout after 10s → retry prompt"&gt;

### 4b. &lt;Next interaction&gt;

&lt;Repeat as needed. Delete unused blocks.&gt;

## 5. Component mapping

Map each UI element to an existing design system component, or flag it as new.

| Element | DS component | Notes |
|---|---|---|
| &lt;e.g., Review card&gt; | `Card/Default` | Standard — no customization |
| &lt;e.g., Status badge&gt; | `Badge/Status` | Add new "pending" variant |
| &lt;e.g., Submit button&gt; | `Button/Primary` | Disabled until form valid |
| &lt;e.g., Feedback toast&gt; | **NEW** — not in DS | Spec below; propose for DS review |

## 6. Content and copy

Final copy for all UI text. Not placeholder. If copy isn't final, mark it `[DRAFT]` and name the owner.

| Location | Copy | Notes |
|---|---|---|
| &lt;e.g., Empty state heading&gt; | &lt;"No reviews yet"&gt; | |
| &lt;e.g., Error message&gt; | &lt;"Something went wrong. Try again."&gt; | |
| &lt;e.g., Success toast&gt; | &lt;"Review submitted"&gt; | Auto-dismiss 3s |

## 7. Accessibility annotations

These are requirements, not nice-to-haves.

- **Focus order:** &lt;describe the tab sequence through the flow — or link to annotated Figma frame&gt;
- **ARIA landmarks:** &lt;e.g., "Review list is `role=feed`; each card is `role=article`"&gt;
- **Screen reader announcements:** &lt;e.g., "On submit success, announce 'Review submitted' via live region"&gt;
- **Keyboard shortcuts:** &lt;if any — e.g., "Enter submits; Escape cancels"&gt;
- **Color contrast:** &lt;confirm all text meets WCAG AA 4.5:1; flag exceptions&gt;
- **Touch targets:** &lt;all interactive elements ≥ 24×24px&gt;
- **Motion:** &lt;respect `prefers-reduced-motion`; list affected animations&gt;

## 8. Responsive behavior

| Breakpoint | What changes |
|---|---|
| Desktop (≥1024px) | &lt;default layout&gt; |
| Tablet (768–1023px) | &lt;e.g., "Card grid collapses to single column"&gt; |
| Mobile (&lt;768px) | &lt;e.g., "Bottom sheet replaces modal"&gt; or "Not in scope — see §2" |

## 9. What's not in Figma but matters

Things the design file doesn't show that engineering needs to know.

- &lt;e.g., "Animation: card entrance is 200ms ease-out fade-in"&gt;
- &lt;e.g., "Optimistic update: show submitted state immediately; revert on error"&gt;
- &lt;e.g., "Data: max 50 reviews loaded; paginate after"&gt;
- &lt;e.g., "Offline: show cached state with 'Last updated' timestamp"&gt;

## 10. Open questions for engineering

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | &lt;e.g., "Can we reuse the existing feed component for the review list?"&gt; | &lt;eng name&gt; | YYYY-MM-DD |
| 2 | | | |

## 11. Sign-off

| Role | Name | Date | Traffic Light |
|---|---|---|---|
| Design lead | | | 🟢 🟡 🔴 |
| Engineering lead | | | 🟢 🟡 🔴 |

---

## Quality check

- [ ] Every screen has all states listed (not just the happy path)
- [ ] Error and loading states are specified for every async interaction
- [ ] Component mapping flags new components explicitly
- [ ] All copy is final (or marked `[DRAFT]` with owner)
- [ ] Accessibility annotations cover focus order, screen reader, contrast, touch targets
- [ ] Responsive behavior documented (or explicitly out of scope)
- [ ] "Not in Figma" section is non-empty

---

*The PRD says what to build. This doc says how it looks and behaves. If engineering has to guess, this handoff isn't done.*

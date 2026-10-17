---
title: "Test Plan — <feature / assumption>"
type: template
template-for: test-plan
status: canonical
owner: Wei Wei
last-updated: 2026-04-21
loop-phase: build
source: Author artifact template; private programme examples omitted
tags: [type/template, type/test-plan, purpose/measure, loop/build, status/canonical]
---

# Test Plan — &lt;feature / assumption being tested&gt;

> **👥 For cross-functional partners**
>
> This is the protocol for testing our build slice *before* we declare it learned from. No test plan, no Learn phase — we'd just be shipping and hoping.

> **TL;DR:** &lt;One sentence — what we're testing, with whom, by when, and what would make us change course.&gt;

## Who reviews what

| Function | Review | Sign-off needed? |
|---|---|---|
| PM | Hypothesis (§2), Metrics (§5), Timeline (§7) | Yes — metrics must match PRD |
| Engineering | Instrumentation (§5), Rollback (§8), Timeline (§7) | Yes — feasibility |
| Research / UX | Method (§3), Tasks (§6), Participants (§4) | Yes — protocol quality |
| Legal / Privacy | Participants (§4) — consent, data handling | Yes — if real users |
| Data / Analytics | Metrics (§5) — can we measure this? | Advisory |

## 1. Metadata

| Field | Value |
|---|---|
| Feature / slice | &lt;name&gt; |
| PRD link | &lt;link&gt; |
| Design handoff link | &lt;link&gt; |
| Test owner | &lt;name&gt; |
| Date | YYYY-MM-DD |
| Status | draft / approved / in-progress / complete |

## 2. What we're testing

### Riskiest assumption

The single assumption from W3 Step 1 this test exists to validate or invalidate.

&lt;e.g., "Ops managers will use async review mode instead of interrupting their team — even when the sync option is still available."&gt;

### Hypothesis

ISE format: *"If we [do X] for [Y users], then we expect [Z metric] to [move in this direction]. We will know this is true when [signal]."*

&lt;...&gt;

## 3. Method

Choose one primary method. Add a secondary only if the primary can't answer the question alone.

| Method | When to use |
|---|---|
| **Usability test** (moderated) | Testing comprehension, flow, findability — qualitative |
| **Unmoderated test** | Testing task completion at scale — quant + qual |
| **A/B experiment** | Testing behavioral change with statistical significance |
| **Dogfood** (internal users) | Testing real-world fit before external exposure |
| **Staged rollout** (smoke test → learning candidate → geo test) | Testing at increasing scale with holdout |

**Primary method:** &lt;...&gt;

**Secondary method (if any):** &lt;...&gt;

## 4. Participants

| Field | Value |
|---|---|
| Who | &lt;persona, segment, or targeting criteria&gt; |
| Sample size | &lt;number + justification — e.g., "8 participants for usability (Nielsen saturation); 5,000 per arm for A/B (power analysis)"&gt; |
| Recruitment | &lt;how — internal panel, UserTesting, customer cohort, feature flag&gt; |
| Exclusions | &lt;who's excluded and why — e.g., "Power users excluded; testing onboarding flow"&gt; |
| Consent | &lt;how consent is obtained; link to consent form if applicable&gt; |

### For A/B experiments

| Field | Value |
|---|---|
| Control group | &lt;what they see — the current experience&gt; |
| Test group(s) | &lt;what each test group sees — one change per group&gt; |
| Allocation | &lt;% per group — e.g., "50/50" or "80 control / 10 test A / 10 test B"&gt; |
| Targeting | &lt;who's eligible — e.g., "English locale, registered > 7 days"&gt; |
| Exposure trigger | &lt;when a user is counted — e.g., "On first view of review inbox"&gt; |

## 5. Metrics

Defined *before* the test runs — not after we see the data.

### Primary metric (the one that answers the hypothesis)

| Metric | Baseline | Target | Window |
|---|---|---|---|
| &lt;e.g., "% of eligible reviews completed async"&gt; | &lt;current&gt; | &lt;goal&gt; | &lt;duration&gt; |

### Counter-metric (must not degrade)

| Metric | Baseline | Must-not-breach |
|---|---|---|
| &lt;e.g., "Review response time"&gt; | &lt;current&gt; | &lt;threshold&gt; |

### Supporting metrics (nice to know)

- &lt;e.g., "Time to first async review"&gt;
- &lt;e.g., "Repeat usage rate"&gt;

### Instrumentation checklist

- [ ] Primary metric instrumented and logging
- [ ] Counter-metric instrumented and logging
- [ ] Supporting metrics instrumented (or explicitly deferred)
- [ ] Data pipeline tested with sample data
- [ ] Dashboard or query ready for read-out

## 6. Tasks / script

For usability tests: the tasks participants will attempt. For A/B: the user flow being changed.

### Usability tasks

| # | Task | Success criteria | Time limit |
|---|---|---|---|
| 1 | &lt;e.g., "Find and complete a pending review"&gt; | &lt;completed without help&gt; | 5 min |
| 2 | &lt;e.g., "Locate a previously submitted review"&gt; | &lt;found within 2 clicks&gt; | 3 min |

### Post-task questions

- &lt;e.g., "On a scale of 1–5, how confident were you that your review was submitted?"&gt;
- &lt;e.g., "What would you change about this experience?"&gt;

## 7. Timeline

| Phase | Dates | Notes |
|---|---|---|
| Test plan approved | YYYY-MM-DD | This doc signed off |
| Recruitment complete | YYYY-MM-DD | |
| Test runs | YYYY-MM-DD → YYYY-MM-DD | &lt;duration + buffer&gt; |
| Analysis | YYYY-MM-DD → YYYY-MM-DD | |
| Read-out / evidence brief | YYYY-MM-DD | Feeds `4-1-Learn_evidence-brief.md` |

### For A/B: staged rollout

| Stage | Audience | Duration | Gate to next |
|---|---|---|---|
| Dogfood | Internal team | &lt;days&gt; | No critical bugs |
| Smoke test | &lt;small external cohort&gt; | &lt;days&gt; | Primary metric trending ≥ baseline |
| Learning candidate | &lt;structured experiment&gt; | &lt;weeks&gt; | Statistical significance reached |
| Holdout / back test | &lt;control group kept after launch&gt; | &lt;weeks&gt; | Confirm long-term effect |

## 8. Rollback trigger

What would make us stop the test early?

- &lt;e.g., "Counter-metric degrades > 10% vs. control"&gt;
- &lt;e.g., "Critical usability failure: > 50% of participants unable to complete Task 1"&gt;
- &lt;e.g., "Ethical concern flagged by participant"&gt;

**Rollback mechanism:** &lt;e.g., "Feature flag off", "Revert PR #NNN"&gt;

## 9. Sign-off

| Role | Name | Date | Traffic Light |
|---|---|---|---|
| Test owner | | | 🟢 🟡 🔴 |
| Engineering lead | | | 🟢 🟡 🔴 |
| Privacy / Legal (if real users) | | | 🟢 🟡 🔴 |

---

## Quality check

- [ ] Riskiest assumption stated in one sentence
- [ ] Hypothesis follows "if…then…we will know when" format
- [ ] Metrics defined *before* the test, not after
- [ ] Counter-metric included (what must not degrade)
- [ ] Instrumentation checklist complete
- [ ] Sample size justified (not "as many as we can get")
- [ ] Rollback trigger is specific, not "if things go bad"
- [ ] Timeline has a read-out date that feeds the evidence brief

---

*Grounded in ISE's Experimentation Design Best Practices (hypothesis → metrics → counter-metrics → targeting → exposure → holdout) and Goaling framework (outcomes not activities, measurable, moveable, falsifiable). A test without a counter-metric is a test that can't fail — and a test that can't fail teaches nothing.*

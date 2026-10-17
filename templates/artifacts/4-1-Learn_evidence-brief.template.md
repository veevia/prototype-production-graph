---
title: "Evidence Brief — <feature / test>"
type: template
template-for: evidence-brief
status: canonical
owner: Wei Wei
last-updated: 2026-04-21
loop-phase: learn
source: Author artifact template; private programme examples omitted
tags: [type/template, type/evidence, purpose/measure, loop/learn, status/canonical]
---

# Evidence Brief — &lt;feature / test name&gt;

> **👥 For cross-functional partners**
>
> This is the 2-page synthesis of what we shipped vs. what we learned. Read time: 5 minutes. The forward-path recommendation is at the bottom — skip there if you're short on time.

> **TL;DR:** &lt;One sentence — what we learned, whether it confirmed or contradicted our hypothesis, and the recommended forward path.&gt;

## Who reads what

| Function | Start here | Why |
|---|---|---|
| PM | §3 Metrics actuals, §6 Forward path | Own the go/no-go |
| Engineering | §2 What shipped, §3 Counter-metric | Confirm nothing degraded |
| Marketing / GTM | §4 What surprised us, §6 Forward path | Shape the external story |
| Executive sponsor | TL;DR + §6 Forward path | Decide: scale, hold, or stop |
| Research / UX | §4 What we learned, §5 Confidence shift | Feed next research cycle |

## 1. Metadata

| Field | Value |
|---|---|
| Feature / slice | &lt;name&gt; |
| Test plan link | &lt;link to `3-1-Build_test-plan.md`&gt; |
| PRD link | &lt;link&gt; |
| Test dates | YYYY-MM-DD → YYYY-MM-DD |
| Author | &lt;name&gt; |
| Date | YYYY-MM-DD |

## 2. What we shipped

Facts only. No interpretation yet.

- **What went live:** &lt;feature description, build slice, fidelity level&gt;
- **Who saw it:** &lt;participant count, segment, method — e.g., "8 moderated usability participants" or "5,000 users per arm, EN locale"&gt;
- **Duration:** &lt;how long the test ran&gt;
- **Release artifacts:** &lt;links — PR, feature flag, Figma prototype used in test&gt;

## 3. What we measured vs. what we promised

Pull directly from the test plan metrics and PRD §6. Actuals go in the table.

### Primary metric

| Metric | Baseline | Target | Actual | Verdict |
|---|---|---|---|---|
| &lt;...&gt; | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; | ✅ met / ❌ missed / ⚠️ inconclusive |

### Counter-metric (guardrail)

| Metric | Baseline | Must-not-breach | Actual | Verdict |
|---|---|---|---|---|
| &lt;...&gt; | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; | ✅ held / ❌ breached |

### Supporting metrics

| Metric | Value | Notes |
|---|---|---|
| &lt;...&gt; | &lt;...&gt; | |

### Measurement gaps

Metrics you intended to collect but couldn't. Say so — don't omit.

- &lt;e.g., "Long-term retention not measurable — test ran 2 weeks; need 8 for signal"&gt;

## 4. What we learned

Interpretation starts here. Separate from §2 (facts) deliberately.

### What confirmed our hypothesis

- &lt;finding + evidence — e.g., "7 of 8 participants completed async review without prompting (observed)"&gt;

### What surprised us

Something always surprises. If nothing did, look harder — or suspect confirmation bias.

- &lt;finding — e.g., "Participants preferred the confirmation toast over the redirect we designed. 6 of 8 mentioned it unprompted."&gt;

### What we got wrong

Hypotheses that didn't hold. Not failures — learning.

- &lt;finding — e.g., "Assumed users would discover the feature from the notification. 3 of 8 never saw the notification; found it through search instead."&gt;

### What we still don't know

Open questions that need the next loop to answer.

- &lt;e.g., "Would the pattern hold for power users? Test excluded them."&gt;
- &lt;e.g., "Is the 2-week adoption curve durable past 30 days?"&gt;

## 5. Confidence shift

Where does this move us on the validation spectrum? (ISE POV model: low → medium → high validation.)

| Before test | After test | What moved it |
|---|---|---|
| &lt;low / medium / high&gt; | &lt;low / medium / high&gt; | &lt;the key evidence&gt; |

### Artifacts to update

Per W4 Step 4 — which Understand/Design artifacts should change based on this evidence?

| Artifact | What changes | Owner |
|---|---|---|
| Journey map | &lt;e.g., "Update Stage 3 pain point — resolved by async flow"&gt; | &lt;name&gt; |
| Persona | &lt;e.g., "Add new quote from participant P5"&gt; | |
| JTBD | &lt;e.g., "No change — hiring criteria confirmed"&gt; | |
| POV | &lt;e.g., "Insight holds; strengthen 'what would make us wrong'"&gt; | |
| PRD | &lt;e.g., "Version-bump: update success metrics with actuals"&gt; | |

## 6. Forward-path recommendation

One of three options. Pick one and argue for it.

### ◻ A. Iterate within Build

Slice was directionally right; refine and re-ship. → Back to W3.

- **What to change:** &lt;...&gt;
- **Riskiest assumption for next slice:** &lt;...&gt;

### ◻ B. Ship wider

Slice validated; widen rollout per PRD staged plan. → Continue W4 measurement.

- **Next rollout stage:** &lt;dogfood → smoke test → learning candidate → geo test → back test&gt;
- **What to watch:** &lt;...&gt;

### ◻ C. Pivot

Evidence invalidates the POV or PRD. → Back to W2 (Design) or W1 (Understand).

- **What broke:** &lt;...&gt;
- **Where to restart:** &lt;Understand / Design&gt;

**Decision:** &lt;A / B / C — owner, evidence, next workflow, and any open conditions&gt;

This brief can retain the forward-path rationale. Phase closure alone needs no new decision file;
use W5 only for a new durable choice needing separate
capture, an explicit capture request, or a lifecycle change.

---

## Sign-off

| Role | Name | Date | Traffic Light |
|---|---|---|---|
| Design lead | | | 🟢 🟡 🔴 |
| PM | | | 🟢 🟡 🔴 |
| Executive sponsor | | | 🟢 🟡 🔴 |

---

## Quality check

- [ ] §2 (shipped) is facts only — no interpretation
- [ ] §3 metrics table has actuals, not just targets
- [ ] Counter-metric reviewed (not just north star)
- [ ] §4 has at least one "got wrong" or "surprised" entry
- [ ] §4 "still don't know" is non-empty
- [ ] §5 confidence shift stated with evidence
- [ ] §5 artifact update table filled (even if "no change")
- [ ] §6 forward path is a single recommendation, not "it depends"
- [ ] Forward path accepted with owner, supporting evidence, and next-workflow reference

---

*What we shipped is not what we learned. This brief separates them. Grounded in ISE's Input → Output → Outcome model and the POV validation spectrum (low → medium → high confidence). An evidence brief with no surprises is either a perfect test or a confirmation-bias report — bet on the second.*

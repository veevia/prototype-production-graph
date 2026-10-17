---
title: "UX Research Report — <topic>"
type: template
template-for: ux-research-report
status: canonical
owner: Wei Wei
last-updated: 2026-04-20
loop-phase: understand
source: Author artifact template; private programme examples omitted
tags: [type/template, type/research, purpose/discover, loop/understand, status/canonical]
---

<!--
  UX RESEARCH REPORT
  Produced during the UNDERSTAND phase. Evidence-first. Every claim is tagged
  observed / reported / assumed.

  Purpose: give the team a single source of truth about users before DESIGN
  begins. If DESIGN work starts without this artifact, expect to rework.

  Remove this comment block before sharing.
-->

# UX Research Report — &lt;topic&gt;

> **👥 For cross-functional partners**
>
> **What this is:** The evidence base from talking to real users. Every claim is tagged as `observed` (we saw it), `reported` (someone told us), or `assumed` (we're guessing).
> **Who owns it:** Design lead / researcher.
> **What we need from you:** Flag findings that contradict what you know from the field. Push back on anything tagged `assumed`. See `GLOSSARY.md` for terms.

> **TL;DR:** &lt;The top insight a stakeholder should walk away with — e.g., "Users don't abandon at checkout for pricing reasons; they abandon because step 3 doesn't tell them what happens next."&gt;

## Who reviews what

| Function | Read | React to |
|---|---|---|
| PM | Findings table (§4), Recommendations (§8) | Flag gaps in field knowledge; challenge priority |
| Engineering | Design implications (§7) — constraints | Flag technical feasibility concerns |
| Marketing / GTM | Key findings (§4), Quotes (§5) | Flag disconnects with market positioning |
| Legal / Privacy | Method (§3) — consent, data handling | Approve research protocol |
| Executive sponsor | TL;DR + Recommendations (§8) | Confirm strategic alignment |

## 1. Metadata

| Field | Value |
|---|---|
| Topic | &lt;what was researched&gt; |
| Researcher | &lt;name&gt; |
| Dates | YYYY-MM-DD → YYYY-MM-DD |
| Methods | &lt;interviews, observation, diary study, analytics review, usability test, survey&gt; |
| Participants | n = &lt;count&gt; — &lt;segment description&gt; |
| Stakeholders | &lt;who commissioned this, who consumes it&gt; |

## 2. Research questions

The questions this research set out to answer. Written before data collection started, not after.

1. &lt;question 1&gt;
2. &lt;question 2&gt;
3. &lt;question 3&gt;

### Working hypothesis

What we believe going in. Stating it upfront prevents confirmation bias from hiding in the analysis.

&lt;e.g., "We believe users abandon at step 3 because the cost is unclear, not because the process is too long."&gt;

**After research, was this confirmed, modified, or invalidated?** &lt;fill after analysis&gt;

## 3. Method

### Approach

&lt;1 short paragraph: what you did and why. Keep defensible; a skeptic should understand sample, protocol, and analysis from this section.&gt;

### Participants

| Segment | n | How recruited |
|---|---|---|
| &lt;segment 1&gt; | | |
| &lt;segment 2&gt; | | |

### Limitations

Name them. Research without stated limitations is over-claiming.

- &lt;e.g., "Convenience sample; skews toward power users"&gt;
- &lt;e.g., "Remote interviews only; no contextual observation"&gt;

## 4. Key findings

Each finding is one sentence with evidence tag. Order by impact, not by interview order.

| # | Finding | Evidence | n supporting | Confidence |
|---|---|---|---|---|
| 1 | &lt;finding&gt; | observed / reported / assumed | &lt;count&gt; of &lt;total&gt; | high / medium / low |
| 2 | ... | ... | ... | ... |
| 3 | ... | ... | ... | ... |

**Evidence tag meanings:**

- **Observed** — participants demonstrated it or said it unprompted
- **Reported** — third party (stakeholder, prior report) claimed it; not directly validated here
- **Assumed** — team hypothesis; listed for traceability, not proven

## 5. Quotes (representative, not cherry-picked)

Quotes support findings; they don't replace them. 3–5 is enough.

> "&lt;quote&gt;" — &lt;participant code, segment&gt;

> "&lt;quote&gt;" — &lt;participant code, segment&gt;

## 6. Journey implications

Which stages of the user journey this changes. Feeds `1-4-Understand_journey-map.template.md`.

| Stage | What changes |
|---|---|
| &lt;stage&gt; | &lt;implication&gt; |

## 7. Design implications

What this tells the DESIGN phase. Not design solutions — design constraints and openings.

- **Constraint:** &lt;something the design must respect&gt;
- **Opening:** &lt;something the design should exploit&gt;
- **Open question:** &lt;what research didn't answer; candidate for next loop&gt;

## 8. Recommendations

Prioritized, with evidence backing each one.

| # | Recommendation | Priority | Evidence (finding #) |
|---|---|---|---|
| 1 | &lt;action&gt; | high / med / low | 1, 3 |

## 8b. HMW statements (filtered by evidence)

Review the HMWs from intake. Keep, revise, or kill each one based on findings. Add new ones if research surfaced problems the intake missed.

> **HMW funnel:** Generate many → **validate with evidence ← you are here** → prioritize through the journey → commit 1–3 in the POV.

| # | HMW | Status | Grounded in finding # |
|---|---|---|---|
| 1 | How might we &lt;...&gt; so that &lt;...&gt;? | keep / revise / kill / new | &lt;finding #&gt; |
| 2 | | | |

## 9. Appendix

- Interview protocol: &lt;link&gt;
- Raw notes (anonymized): &lt;link&gt;
- Analytics queries: &lt;link&gt;
- Consent and data handling: &lt;link&gt;

---

## Quality check (before sharing)

- [ ] TL;DR passes the 10-second test
- [ ] Every finding has an evidence tag (observed / reported / assumed)
- [ ] Limitations section is filled (not "none")
- [ ] At least one finding is inconvenient for the commissioning team (if none, research is probably confirmation-biased)
- [ ] Recommendations are traceable to findings by number
- [ ] HMW statements filtered against findings (none carried from intake without evidence check)
- [ ] No claim uses "users want" without an observed quote or behavior to back it

---

*Template grounded in ISE design research standards and UX research discipline. Feeds `persona`, `jtbd`, and `user-journey-map` in the UNDERSTAND phase.*

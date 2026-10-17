---
doc: experience
status: filled
project: Lot Release Workbench (fictional example)
---

# Experience — Lot Release Workbench (fictional example)

> **TL;DR:** A reviewer opens a lot from the queue, sees every value next to its limit with an explained verdict, and records a guarded decision.

## Journeys

- **Receive** — A lot and its certificate arrive. Pain: Certificates are PDFs. Opportunity: Queue lots with a derived verdict.
- **Review** — Compare each value with the specification. Pain: Re-keying, 6 of 11 minutes (E-02). Opportunity: Values next to limits.
- **Decide** — Release, hold or reject. Pain: Missed out-of-spec values (E-03). Opportunity: A guarded, explained decision.
- **Notify** — Tell the supplier. Pain: Drafts written from scratch. Opportunity: A generated draft, sent by supplier quality.
- **Audit** — Show who decided what. Pain: Phone escalations leave no trace (E-06). Opportunity: A decision log.

## Tasks

Release a compliant lot · hold an out-of-spec lot and draft the notice · escalate an unreadable certificate · find a lot.

## Information architecture

| Screen id | Name | Route | Purpose | Parent |
|---|---|---|---|---|
| queue | Lot queue | `#/queue` | See incoming lots with their derived verdict; find the next lot to review | — |
| lot | Lot review | `#/lot/L-2418` | Compare every result with its limit, read the verdict, record the decision | queue |
| notice | Supplier notice draft | `#/lot/L-2431/notice` | Prepare the supplier notice for a held lot (never sent from here) | lot |
| audit | Decision log | `#/audit` | See every decision, who made it, when, and the verdict at the time | — |

**Navigation:** Lot queue · Decision log.

## User flows

- **F-01 Release a compliant lot** (R-01, R-02, R-03, R-06): queue: Filter to Needs review and open the lot → lot: Read results next to limits and the derived verdict → lot: Choose Release, add a rationale, record → audit: Open the decision log
- **F-02 Hold an out-of-spec lot and draft the notice** (R-01, R-02, R-03, R-04, R-07): lot: See the out-of-spec result and the Hold verdict → lot: Choose Hold with a rationale of at least 20 characters → notice: Draft the supplier notice and save it
- **F-03 Escalate an unreadable certificate** (R-05, R-04): lot: See the missing result and the Escalate verdict → lot: Try a hold with a short rationale
- **F-04 Find a lot and recover** (R-09, R-08): queue: The first load fails; retry → queue: Search with no match, then reset

## System behavior

- The verdict is derived: any out-of-spec result → Hold; any missing or unreadable result → Escalate (never lower); otherwise Ready
- Release is guarded: allowed only when the verdict is Ready
- Decisions persist in the browser and appear in the log
- Notices are drafts; nothing is ever sent

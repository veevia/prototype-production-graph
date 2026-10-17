# Copy deck — Lot Release Workbench (fictional)

> **TL;DR:** The words reviewers see, in their own vocabulary: lot, certificate, specification, release, hold, reject.

Source of terms: the fictional reviewer interviews (`sources/research/reviewer-interviews.md`) and the lot-release SOP
(`sources/process/lot-release-sop.md`). Every string here appears in the prototype; none is placeholder text.

## Global

| Key | Text |
|---|---|
| product | Lot Release Workbench |
| org | Fabrikam Beverages · Riverside plant (fictional) |
| synthetic | **Synthetic data.** Fictional lots, suppliers and certificates, for design review only. |
| nav.queue | Lot queue |
| nav.audit | Decision log |
| footer | Prototype build … Decisions are stored in this browser only. |
| footer.storage-off | Decisions are not being saved: storage is unavailable in this browser. |
| storage.warning | Decisions can't be saved in this browser. Storage is unavailable, so decisions last only until you close this tab. Record them in the paper log as well. |
| reset.confirm | Erase N recorded decision(s) and M saved notice draft(s) from this browser? This cannot be undone. |

## Lot queue

| Key | Text |
|---|---|
| lede | Incoming ingredient lots with their supplier certificates of analysis. The verdict is derived from each certificate against its specification; the decision is yours. |
| filters | All · Needs review · On hold · Released · Rejected |
| search.label | Search |
| search.hint | Lot, certificate, material or supplier |
| loading | Loading lots… |
| error.title | The lot list did not load |
| error.body | The plant server did not answer (simulated). Nothing you recorded was lost. |
| error.action | Try again |
| empty.title | No lots match |
| empty.action | Reset filters |
| note | Showing N of M lots · needs review first, then by verdict (escalate, hold, ready) and review due date. |

## Lot review

| Key | Text |
|---|---|
| panel.title | Verdict and decision |
| verdict.ready | Ready to release |
| verdict.hold | Hold |
| verdict.escalate | Escalate to QA lead |
| verdict.rule | Any out-of-spec result → Hold. Any missing or unreadable result → Escalate (missing data never lowers the tier). Otherwise → Ready. You make the decision. |
| table.title | Certificate results against specification |
| result | Within · Borderline · Out of spec · Missing |
| decision.legend | Choose a decision |
| release.locked | Release unlocks when every result is within specification. |
| rationale.label | Rationale — required for hold and reject, at least 20 characters |
| rationale.error | Write a rationale of at least 20 characters (N so far). |
| submit | Record decision |
| recorded | Decision recorded: lot … |
| notice.link | Draft supplier notice |

## Supplier notice

| Key | Text |
|---|---|
| banner | **Draft only.** Sending happens outside this prototype; nothing leaves this page. |
| issues.title | What needs the supplier's action |
| save | Save draft |
| saved | Draft saved — not sent |
| decision.none | No decision recorded for this lot yet. |
| closing.hold | Please send a corrected certificate or a retest result. The lot stays on hold until then. |
| closing.reject | We have rejected this lot. Please arrange its collection, and send a corrective action for future deliveries. |
| closing.none | Please send a corrected certificate or a retest result. No release decision has been recorded yet. |

## Decision log

| Key | Text |
|---|---|
| lede | Every decision, who made it, when, and the derived verdict at that moment. Newest first. |
| empty.title | No decisions recorded yet |
| previous | Previous shift |
| note | N decisions this session · M from the previous shift (synthetic). |

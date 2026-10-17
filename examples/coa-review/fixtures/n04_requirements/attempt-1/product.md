## Requirements

| ID | Type | Priority | Requirement | Evidence / assumption | Acceptance |
|---|---|---|---|---|---|
| R-01 | user | P0 | Show every certificate result next to its specification limit, with its result | E-01, E-04 | Each parameter row shows the specification, the certificate value and the result; No value has to be re-keyed |
| R-02 | user | P0 | Derive a verdict (ready, hold, escalate) and show how it was derived | E-07, A-01 | The verdict names the results that drive it; Each row shows its derivation |
| R-03 | business | P0 | Allow release only when every result is within specification | E-03, E-05 | Release is disabled with an 'unlocks when' reason otherwise |
| R-04 | business | P0 | Require a rationale of at least 20 characters for hold and reject | E-05 | A shorter rationale is refused with a message, and focus moves to the field |
| R-05 | user | P0 | Escalate lots with a missing or unreadable result to the QA lead, never lowering the tier | E-06 | An unreadable value makes the verdict 'Escalate to QA lead' |
| R-06 | business | P0 | Record every decision with the reviewer, the time, the rationale and the verdict at that moment | E-05 | The decision log lists every decision, newest first |
| R-07 | user | P1 | Draft the supplier notice from the results that need action, and never send it from the tool | E-08, A-03 | The draft lists every result that needs action; No send control exists |
| R-08 | technical | P0 | Run offline in a browser from one file on the plant tablets | E-10 | Opens from file:// with zero network requests |
| R-09 | user | P1 | Filter the queue by status and search it, with a way back from an empty result | E-11, A-04 | An empty result offers 'Reset filters' |

## Constraints

| ID | Type | Constraint | Source |
|---|---|---|---|
| C-01 | technical | No internet on plant tablets | S-05 SOP §6 (E-10) |
| C-02 | regulatory | Decisions must be attributable to a named reviewer with a time | S-05 SOP §3 |
| C-03 | time | Pilot-ready prototype in six weeks | S-01 brief |
| C-04 | design | Use the Fabrikam Quality UI guide | S-07 |


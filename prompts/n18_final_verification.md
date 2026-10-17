# n18_final_verification — Final verification and delivery

You are the **technical-qa** agent. Your task packet (`.pdg/tasks/n18_final_verification-a<n>.md`) has the inputs, the output
schemas, the quality bar and the exact submit command. The engine, not you, decides when the work is done.

## Method

1. Deterministic: every release condition is recomputed from disk (gate, defects, current reviews, hashes, ledger, controls).
2. The package holds the prototype, the control documents and the evidence, with a sha256 manifest.
3. The release summary leads with a TL;DR and lists non-human approvals, simulated sessions and pending human dimensions.
4. Wei releases the version or requests changes with feedback (which loops back to diagnosis).

## Check before you submit

- [ ] All conditions ✓
- [ ] Manifest verifies

## Never

- Release on an agent's 'done'
- Hide a dry-run approval

# n17_targeted_rework — Targeted redesign or redevelopment

You are the **orchestrator** agent. Your task packet (`.pdg/tasks/n17_targeted_rework-a<n>.md`) has the inputs, the output
schemas, the quality bar and the exact submit command. The engine, not you, decides when the work is done.

## Method

1. Deterministic: the plan re-opens only the traced regeneration targets (a design node = redesign; a build node = redevelopment).
2. Each target's next packet carries its defects with the smallest fix and the acceptance check.
3. Descendants re-run only when their fingerprint changed; everything else is memo-skipped.

## Check before you submit

- [ ] Targets = traced nodes only

## Never

- Re-open an untraced node

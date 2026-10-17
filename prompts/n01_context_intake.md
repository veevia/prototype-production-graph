# n01_context_intake — Context intake

You are the **context-research** agent. Your task packet (`.pdg/tasks/n01_context_intake-a<n>.md`) has the inputs, the output
schemas, the quality bar and the exact submit command. The engine, not you, decides when the work is done.

## Method

1. Read `sources/brief.md` verbatim. Do not paraphrase it into the registry.
2. Pull project context just in time: `/context-pull <program> "<topic>"`, then read only the pages it returns.
3. Register every file you rely on with `kind` and an evidence tag: `observed` (direct user evidence), `reported` (someone's claim), `assumed` (the team's hypothesis).
4. Register a design-system or brand authority (for example your design system's AI instructions, as `templates/artifacts/DESIGN-SYSTEM-AI-INSTRUCTIONS.md` describes, copied into `sources/`) when one applies.
5. List open questions; mark `blocking: true` only when the product cannot be defined without the answer.

## Check before you submit

- [ ] Every local path exists inside the project
- [ ] The brief is registered
- [ ] No source is invented, and no quote lacks a source

## Never

- Summarise a source instead of registering it
- Quote confidential meeting content outside a `*_TENANT` file
- Fill a gap with plausible invention

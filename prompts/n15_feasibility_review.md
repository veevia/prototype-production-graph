# n15_feasibility_review — Technical feasibility review

You are the **front-end-engineer** agent. Your task packet (`.pdg/tasks/n15_feasibility_review-a<n>.md`) has the inputs, the output
schemas, the quality bar and the exact submit command. The engine, not you, decides when the work is done.

## Method

1. Read `feasibility-report.json` (syntax, unit tests, bundle size, network references, development.md sections).
2. Review correctness, readability, architecture, security and performance of the prototype code. A unit test that cannot fail guards nothing: for each rule-guarding test, check that breaking the rule makes it fail.
3. Name every mocked seam (persistence, APIs, auth, audit sink) and what production needs for it. Read glue code for writes to the page's text or visibility: code that rewrites copy to satisfy a test is a finding.
4. File findings with trace, smallest fix and acceptance check for blocking risks; give each its `element` (file or function) when one location has several.
5. State `reviewer` and `independent: true` only if you wrote none of the code under review.
   When you measure a box in your own probe, use `getBoundingClientRect()` less borders and padding and allow 0.5 px: `clientWidth` rounds, so a box sized exactly to its text (`field-sizing: content`) can read up to 0.5 px short and look cut when it is not (field run W57). Say which measure a finding used. A select's content box includes its native arrow: to see whether its value fits, compare it with a copy sized to its content (`field-sizing: content`), as RESP-TEXT does.
6. Run any Python probe against a registered build with `python -B` (or from a copy in `/tmp`) so the probe writes no bytecode cache into the artifact.

## Check before you submit

- [ ] Every MUST review dimension scored
- [ ] Mocked seams named

## Never

- Call the prototype production-ready

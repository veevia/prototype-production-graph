# n10_prototype_planning — Prototype planning

You are the **prototype-developer** agent. Your task packet (`.pdg/tasks/n10_prototype_planning-a<n>.md`) has the inputs, the output
schemas, the quality bar and the exact submit command. The engine, not you, decides when the work is done.

## Method

1. Follow the test-plan template: riskiest assumption, hypothesis, method, metrics, rollback trigger.
2. Choose the fidelity the evidence supports. Mid or high fidelity needs every riskiest assumption validated (or accepted as a risk by a named human); high needs customer alignment evidence.
   A risk counts as accepted only when Wei records it himself (`pdg accept-risk <project> <A-xx> --actor Wei --reason "…"`).
   Writing `accepted_by` or quoting Wei does not count; if a risk needs accepting, say so in prototype.md and let the
   gate ask him.
3. Write scenarios `S-xx` in the step DSL (goto · click · fill · press · select · expect_visible · expect_text · expect_no_text · expect_count · expect_disabled · expect_enabled · expect_route · expect_focus · expect_in_viewport · expect_reachable · screenshot · axe); ≥ 1 per P0 flow, each ending in an expectation. Only a scenario's first `goto` loads the page cold. A later `goto` that changes only the `#` route keeps the app's state, as a link does; one that changes the `?query` or drops the `#` loads the page again; one to the URL the page is already on returns to the top with focus released (a browser does not navigate to the page it is on). Use `reload` to test a fresh load.
   For each record screen, name in `samples` 2–3 other records most likely to break the layout (the most actions or pills, the longest title, a missing field), never a design screen's own route: the width checks (320 px, and the band below and between your planned widths) load them as well as the design's route, and as well as records the app links to under the same route. A sample that does not show its screen alone is dropped and named.
   Before a P0 scenario's last click, check that control with `expect_reachable` (within one screen of where the user is) or `expect_in_viewport` (in view without scrolling): a completing action far below the fold still passes a click, because the browser scrolls to it. List in `forbidden_text` every text a P0 requirement says must never show (retired records, placeholder names): the suite scans every screen and state for it.
4. List the states to reach (screen, state, route, marker selector), the viewports (≤ 400 px and ≥ 1280 px), the content needs and measurable test criteria.
   Where N08 says a status message is announced (a count after a filter, a saved status), check its live region (a
   `role="status"` or `role="alert"` element, an `aria-live` one, or an `<output>`), by that region's own selector:
   `expect_text` with `""` on it before the trigger, since a region added together with its text is not announced, and
   `expect_text` with the message after it. A message the app sets after a delay (a debounced filter) is traced to
   A11Y-MANUAL instead: `expect_text` reads once. A count N08 called announced was announced on 1 list of 4, and no step
   checked it (field run 2, R2-31).
   Give every empty state its way back as `recover: {click: "<selector>"}` (and `expect_hidden` if something other than its marker disappears): the suite presses it and expects the state gone. The suite also focuses each state's first control and watches it for a second: it must keep focus and stay still.
5. Trace every N08 focus rule, verbatim, in `focus_trace`: to the `expect_focus` step that checks it (`scenario` + 1-based `step`), to the browser check that covers it (`covered_by: A11Y-FOCUS` or `A11Y-FOCUS-VISIBLE-2411`, for a rule about the focus indicator), or to `out_of_scope` with the reason. PLN-FOCUS fails an untraced rule.
   Trace every P0 acceptance line from N04, verbatim with its requirement id, in `acceptance_trace`: to an expectation step (`scenario` + 1-based `step`), to a `forbidden_text` entry (a naming or "never shows" line: one entry covers every screen and state), to `covered_by` a check a later node runs (for example `FUNC-OFFLINE` or the N13 review `DES-DERIVATION`), or to `out_of_scope` with the reason. PLN-ACCEPTANCE fails an untraced P0 line; trace P1 lines too, since untraced ones are listed.
6. Write your copy of `prototype.md` in your work folder (start from `controls/prototype.md`); Wei's approval locks it.

## Check before you submit

- [ ] The fidelity gate holds
- [ ] Every P0 flow has an executable scenario
- [ ] Every data screen's empty and error states are planned
- [ ] Every empty state has a `recover` way back, and every N08 focus rule is in `focus_trace`
- [ ] Every P0 acceptance line is in `acceptance_trace` (and every P1 line you can)

## Never

- Raise fidelity on an untested core assumption
- Plan a scenario that only checks that a page loads

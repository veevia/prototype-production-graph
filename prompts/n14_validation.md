# n14_validation — User and stakeholder validation

You are the **context-research** agent. Your task packet (`.pdg/tasks/n14_validation-a<n>.md`) has the inputs, the output
schemas, the quality bar and the exact submit command. The engine, not you, decides when the work is done.

## Method

1. Run the moderator guide with named participants (role + anonymised id). Think-aloud; don't demonstrate.
2. Per task record: scenario id, success, time, SEQ (1–7) and quotes. Five users per round finds most problems (NN/g).
   Draw any post-session questions (outcomes, jobs, pain points) from the UX survey template
   (`00_README/_templates/1-2-Understand_UX_survey.template.md` §2–4); never add questions the plan did not ask for.
3. Record stakeholder concerns as findings with `by: human` and the participant; each traced to the node it implicates.
4. Mark every session `simulated: true|false` honestly. A simulated session is never user evidence.
5. Append the validation findings to your work-folder copy of `research.md` (start from `controls/research.md`; the section is append-only).
6. Put findings in the validation doc; the review carries the scores. State `reviewer` and `independent: true` only if you produced none of the work under review. Findings from a simulated session are labelled by the engine.
7. Run any Python probe against a registered build with `python -B` (or from a copy in `/tmp`) so the probe writes no bytecode cache into the artifact.

## Check before you submit

- [ ] Every task maps to a planned scenario
- [ ] Every session has the simulated flag set honestly

## Never

- Play the user yourself and report it as a participant
- Drop an unfavourable quote

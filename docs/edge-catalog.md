# Edge catalog

> **TL;DR:** All edges, generated from `graph/workflow.yaml`. Flow edges form a DAG with join = all; loop edges are bounded; escalate edges stop the run.

| ID | From → To | Kind | Transition | When | Transfers | Threshold | Branch / retry / rollback / approval | Max |
|---|---|---|---|---|---|---|---|---|
| E01 | `START` → `n01_context_intake` | flow | deterministic | `*` | the brief; sources/ | sources/brief.md exists | Opens the run | — |
| E02 | `n01_context_intake` → `n02_evidence_review` | flow | deterministic | `*` | artifact:sources; state:inputs.sources | Registry schema-valid; every source tagged | Forward | — |
| E03 | `n02_evidence_review` → `n01_context_intake` | loop | conditional | `gaps_resolvable` | artifact:gaps | At least one resolvable gap | Retry intake with the gap list; the inputs stay unfrozen | 2 |
| E04 | `n02_evidence_review` → `n03_problem_definition` | flow | conditional | `pass` | artifact:evidence; state:research.*; the inputs sha256 | No blocking or resolvable gap; inputs frozen | Branch: pass | — |
| E05 | `n02_evidence_review` → `@escalate` | escalate | conditional | `gaps_blocking` | artifact:gaps | A blocking gap | Escalate to Wei; the run is BLOCKED until a source is registered or the gap is waived | — |
| E06 | `n03_problem_definition` → `n04_requirements` | flow | conditional | `approved` | artifact:problem; state:product.problem | Wei approved the problem frame | Approval: forward | — |
| E07 | `n03_problem_definition` → `n03_problem_definition` | loop | conditional | `rejected` | Wei's rejection reason | Wei rejected the frame | Retry the frame with Wei's reason | 2 |
| E08 | `n04_requirements` → `n05_scope_success` | flow | deterministic | `*` | artifact:requirements; state:product.requirements | Every requirement traced; every P0 has acceptance criteria | Forward | — |
| E09 | `n05_scope_success` → `n06_concept_ideation` | flow | conditional | `approved` | artifact:scope; product.md and evaluation.md (locked) | Wei signed the scope | Approval: forward; product.md and evaluation.md lock | — |
| E10 | `n05_scope_success` → `n04_requirements` | loop | conditional | `rejected` | Wei's rejection reason | Wei rejected the scope | Rollback to requirements with Wei's reason | 2 |
| E11 | `n06_concept_ideation` → `n07_experience_architecture` | flow | conditional | `approved` | artifact:concepts; state:design.selected_concept | Wei chose a concept | Approval: forward | — |
| E12 | `n06_concept_ideation` → `n06_concept_ideation` | loop | conditional | `rejected` | Wei's rejection reason | Wei rejected every concept | Re-ideate with Wei's reason | 2 |
| E13 | `n07_experience_architecture` → `n08_interaction_design` | flow | deterministic | `*` | artifact:experience; state:design.screens; state:design.flows | Every P0 requirement covered by a flow | Fan-out (1 of 2) | — |
| E14 | `n07_experience_architecture` → `n09_visual_system` | flow | deterministic | `*` | artifact:experience; state:design.screens | Screen inventory complete | Fan-out (2 of 2); runs in parallel with N08 | — |
| E15 | `n08_interaction_design` → `n10_prototype_planning` | flow | deterministic | `*` | artifact:interactions; state:design.interactions | Every screen has states and keyboard behaviour | Fan-in (1 of 2): join = all | — |
| E16 | `n09_visual_system` → `n10_prototype_planning` | flow | conditional | `approved` | artifact:design_system; design.md (locked) | Wei approved the visual system | Fan-in (2 of 2): join = all; design.md locks | — |
| E17 | `n09_visual_system` → `n09_visual_system` | loop | conditional | `rejected` | Wei's rejection reason | Wei rejected the visual system | Retry the visual system with Wei's reason | 2 |
| E18 | `n10_prototype_planning` → `n11_prototype_development` | flow | conditional | `approved` | artifact:plan; prototype.md (locked) | Wei approved the fidelity and the plan | Approval: forward; prototype.md locks | — |
| E19 | `n10_prototype_planning` → `n10_prototype_planning` | loop | conditional | `rejected` | Wei's rejection reason | Wei rejected the plan | Replan with Wei's reason (lowering the fidelity is a valid fix) | 2 |
| E20 | `n11_prototype_development` → `n12_content_data` | flow | deterministic | `*` | artifact:prototype_build; artifact:build_manifest | Static checks and unit tests pass | Forward | — |
| E21 | `n12_content_data` → `n13_quality_review` | flow | deterministic | `*` | artifact:prototype (build version N) | Content checks pass | Fan-out (1 of 3) | — |
| E22 | `n12_content_data` → `n14_validation` | flow | deterministic | `*` | artifact:prototype (build version N); artifact:plan | Content checks pass | Fan-out (2 of 3); parallel | — |
| E23 | `n12_content_data` → `n15_feasibility_review` | flow | deterministic | `*` | artifact:prototype; artifact:prototype_build | Content checks pass | Fan-out (3 of 3); parallel | — |
| E24 | `n13_quality_review` → `n16_feedback_diagnosis` | flow | deterministic | `*` | review record; tool findings | Review complete for build version N | Fan-in (1 of 3): join = all | — |
| E25 | `n14_validation` → `n16_feedback_diagnosis` | flow | deterministic | `*` | review record; validation sessions | Review complete for build version N | Fan-in (2 of 3): join = all | — |
| E26 | `n15_feasibility_review` → `n16_feedback_diagnosis` | flow | deterministic | `*` | review record; feasibility report | Review complete for build version N | Fan-in (3 of 3): join = all | — |
| E27 | `n16_feedback_diagnosis` → `n18_final_verification` | flow | conditional | `pass` | artifact:gate_report | No blocking defect open; every review current | Branch: pass | — |
| E28 | `n16_feedback_diagnosis` → `n17_targeted_rework` | flow | conditional | `rework` | artifact:gate_report; the routable defects | Blocking defects with routable traces and budget left | Branch: rework | — |
| E29 | `n16_feedback_diagnosis` → `@escalate` | escalate | conditional | `blocked` | artifact:gate_report; rework history | A defect needs Wei, failed 3 corrections, or the cycle budget is spent | Escalate; the run is BLOCKED | — |
| E30 | `n17_targeted_rework` → `n03_problem_definition` | loop | conditional | `target:n03_problem_definition` | defects traced to the problem frame | An open defect traces here | Redesign: re-open the problem frame and its descendants | 4 |
| E31 | `n17_targeted_rework` → `n04_requirements` | loop | conditional | `target:n04_requirements` | defects traced to a requirement | An open defect traces here (product.md is locked: a change request comes first) | Redesign: re-open requirements and descendants | 4 |
| E32 | `n17_targeted_rework` → `n05_scope_success` | loop | conditional | `target:n05_scope_success` | defects traced to scope or success criteria | An open defect traces here (locked documents need a change request) | Redesign: re-open scope and descendants | 4 |
| E33 | `n17_targeted_rework` → `n06_concept_ideation` | loop | conditional | `target:n06_concept_ideation` | defects traced to the concept | An open defect traces here | Redesign: re-open the concept and descendants | 4 |
| E34 | `n17_targeted_rework` → `n07_experience_architecture` | loop | conditional | `target:n07_experience_architecture` | defects traced to flows or IA | An open defect traces here | Redesign: re-open the experience architecture and descendants | 4 |
| E35 | `n17_targeted_rework` → `n08_interaction_design` | loop | conditional | `target:n08_interaction_design` | defects traced to interactions or states | An open defect traces here | Redesign: re-open the interaction spec and descendants | 4 |
| E36 | `n17_targeted_rework` → `n09_visual_system` | loop | conditional | `target:n09_visual_system` | defects traced to tokens or components | An open defect traces here (design.md is locked: a change request comes first) | Redesign: re-open the visual system and descendants | 4 |
| E37 | `n17_targeted_rework` → `n10_prototype_planning` | loop | conditional | `target:n10_prototype_planning` | defects traced to the plan | An open defect traces here (prototype.md is locked: a change request comes first) | Replan and re-open descendants | 4 |
| E38 | `n17_targeted_rework` → `n11_prototype_development` | loop | conditional | `target:n11_prototype_development` | defects traced to the implementation | An open defect traces here | Redevelopment: re-open the build and descendants | 4 |
| E39 | `n17_targeted_rework` → `n12_content_data` | loop | conditional | `target:n12_content_data` | defects traced to content or data | An open defect traces here | Redevelopment: re-open content integration and descendants | 4 |
| E40 | `n17_targeted_rework` → `@escalate` | escalate | conditional | `no_target` | the unroutable defects | No routable target | Escalate; the run is BLOCKED | — |
| E41 | `n18_final_verification` → `n19_learning_memory` | flow | conditional | `approved` | artifact:release_report; artifact:package | Wei released the version | Approval: forward | — |
| E42 | `n18_final_verification` → `n16_feedback_diagnosis` | loop | conditional | `changes_requested` | Wei's feedback, recorded as feedback items | Wei requested changes | Rollback to diagnosis: the feedback becomes traced defects | 2 |
| E43 | `n19_learning_memory` → `END` | flow | deterministic | `*` | artifact:lessons; artifact:learning_proposal | Lessons evidenced | Ends the run | — |

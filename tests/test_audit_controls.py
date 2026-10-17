"""Control documents: a heading inside a fenced code block (or a YAML comment in front matter) is text, not a section
boundary. Otherwise an owned section loses everything after the fenced line when it is merged, and an append-only
section ends early, so the lines after the fence can be deleted or rewritten unnoticed (audit finding F01)."""

from __future__ import annotations

from pdg.controls import append_only_sections, append_only_violations, merge_sections, split_sections

ACCEPTED_PRODUCT = """# Product

## Problem
Releasers re-key certificate values by hand.

## Requirements
- R-01 Show the certificate beside the lot.
"""

SUBMITTED_REQUIREMENTS = """# Product

## Requirements
- R-01 Show the certificate beside the lot.
- Example of the import format:

```text
## regenerate when the supplier changes
lot,value
```

- R-02 Flag any value outside its specification.
"""


def test_a_fenced_heading_inside_an_owned_section_does_not_split_it():
    merged, ignored = merge_sections(ACCEPTED_PRODUCT, SUBMITTED_REQUIREMENTS, ["Requirements", "Constraints"])
    assert ignored == []
    assert "- R-02 Flag any value outside its specification." in merged     # nothing after the fence is dropped
    assert merged.count("```") == 2                                         # and the fence stays closed
    assert "Releasers re-key certificate values by hand." in merged        # the other writer's section is untouched
    assert [t for t, _ in split_sections(merged)[1]] == ["Problem", "Requirements"]


EVIDENCE_LOG = """# Research

## Evidence log
<!-- append-only -->
- E-01 Interview: releasers copy values from a PDF.
~~~~
# raw export (kept verbatim)
```
still inside the tilde fence
~~~~
- E-02 Analytics: 14% of lots are re-keyed twice.
- E-03 Survey: 9 of 12 releasers want a side-by-side view.

## Open questions
- Q-01 Who signs the second check?
"""


def test_a_fenced_heading_cannot_end_an_append_only_section():
    body = append_only_sections(EVIDENCE_LOG)["Evidence log"]
    assert "- E-03 Survey: 9 of 12 releasers want a side-by-side view." in body
    rewritten = EVIDENCE_LOG.replace("- E-02 Analytics: 14% of lots are re-keyed twice.\n", "").replace(
        "9 of 12", "12 of 12")
    errs = append_only_violations(EVIDENCE_LOG, rewritten)
    assert errs and "Evidence log" in errs[0] and "lost 2 line(s)" in errs[0]


def test_yaml_comments_in_front_matter_are_not_headings():
    doc = "---\nthresholds:\n## comment inside the front matter\n  browser: {min_text_px: 12}\n---\n# Evaluation\n\n## Gates\n- G-1\n"
    pre, secs = split_sections(doc)
    assert [t for t, _ in secs] == ["Gates"] and "## comment inside the front matter" in pre


def test_a_document_that_only_starts_with_a_rule_still_has_sections():
    doc = "---\n# Notes\n\n## Decisions\n- D-1\n"                        # no closing '---': not front matter
    assert [t for t, _ in split_sections(doc)[1]] == ["Decisions"]


def test_fences_close_only_on_the_same_character_and_length():
    doc = "## A\n````\n```\n## not a heading\n````\n## B\n"
    assert [t for t, _ in split_sections(doc)[1]] == ["A", "B"]


def test_every_canonical_template_a_control_document_names_exists():
    """Each control document declares the canonical templates of Wei's method it follows (front matter). A renamed or
    removed template must fail here, not leave agents pointed at nothing."""
    from pathlib import Path

    import pytest

    from pdg.controls import TEMPLATES, front_matter
    workspace = Path(__file__).resolve().parents[3]
    if not (workspace / "00_README" / "_templates").is_dir():
        pytest.skip("the workspace templates are not in this checkout")
    named = {ref for t in TEMPLATES.glob("*.md") for ref in front_matter(t.read_text()).get("canonical_templates", [])}
    assert len(named) >= 12
    assert [ref for ref in sorted(named) if not (workspace / ref).is_file()] == []


def _submission(project, tmp_path, doc: str, replace: tuple[str, str]):
    from pdg.engine import Engine
    eng = Engine(project)
    text = eng.controls.accepted_text(doc)
    assert replace[0] in text, replace[0]
    src = tmp_path / f"{doc}.submitted.md"
    src.write_text(text.replace(*replace, 1))
    return eng, src


def test_a_submission_that_leaves_a_code_fence_open_is_refused(project, tmp_path):
    """An open fence in one writer's section would swallow every later section, other writers' included (N1)."""
    eng, src = _submission(project, tmp_path, "product", ("## Users\n", "## Users\n```text\nexport format, never closed\n"))
    node = eng.node("n03_problem_definition")
    errs = eng.controls.check_install(node.id, node.controls.write, "product", src)
    assert errs and "never closed" in errs[0]


def test_a_submission_with_a_repeated_section_heading_is_refused(project, tmp_path):
    """A merge keeps one copy of a repeated heading, so the other copy's text would be dropped silently."""
    eng, src = _submission(project, tmp_path, "product", ("## Users\n", "## Users\n- a first copy\n\n## Users\n"))
    node = eng.node("n03_problem_definition")
    errs = eng.controls.check_install(node.id, node.controls.write, "product", src)
    assert errs and "appear more than once" in errs[0] and "Users" in errs[0]


def test_a_fence_closed_only_after_a_form_feed_or_line_separator_is_still_open(project, tmp_path):
    """The check and the merge split lines the same way ("\n" only), so a fence that str.splitlines() would call closed
    after a form feed or U+2028 is refused instead of silently swallowing the later sections (N1 residual)."""
    for sep in ("\x0c", "\u2028"):
        eng, src = _submission(project, tmp_path, "product",
                               ("## Users\n", f"## Users\n```text\nexport sample{sep}```\n"))
        node = eng.node("n03_problem_definition")
        errs = eng.controls.check_install(node.id, node.controls.write, "product", src)
        assert errs and "never closed" in errs[0], repr(sep)

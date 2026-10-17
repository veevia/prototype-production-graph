"""The real browser suite (Chromium + axe-core, no stubs). The corrected build passes every browser dimension at
every planned viewport; the draft build's overlay fails colour contrast on the queue, traced to prototype development,
which is exactly the defect the dry run's first gate routes back. Slow (~25 s): real pages, real measurements."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from pdg.context import CheckResult
from pdg.tools import browser

from .conftest import EXAMPLE, PKG

pytest.importorskip("playwright")
FIX = EXAMPLE / "fixtures"


def _build(tmp: Path, overlay: bool) -> tuple[Path, dict]:
    out = tmp / ("draft" if overlay else "corrected")
    cmd = [sys.executable, str(EXAMPLE / "prototype" / "build.py"), "--src", str(EXAMPLE / "prototype"), "--out", str(out)]
    if overlay:
        cmd += ["--overlay", str(FIX / "n11_prototype_development" / "attempt-1" / "overlay")]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    man = json.loads((out / "build-manifest.json").read_text())
    return out / man["entry"], man


def _suite(entry: Path, out: Path, viewports: list[int], plan_attempt: int = 2) -> tuple[dict, CheckResult]:
    plan = json.loads((FIX / "n10_prototype_planning" / f"attempt-{plan_attempt}" / "plan.json").read_text())
    exp = json.loads((FIX / "n07_experience_architecture" / "attempt-1" / "experience.json").read_text())
    screens = browser.suite_screens(exp["screens"], plan.get("samples"))   # as N13 builds them: kinds, so records are sampled
    t = yaml.safe_load((PKG / "config" / "defaults.yaml").read_text())["thresholds"]["browser"]
    try:
        ds = json.loads((FIX / "n09_visual_system" / "attempt-1" / "design-system.json").read_text())
        rep = browser.run_suite(entry, plan["scenarios"], plan["states"], screens, viewports, t, out,
                                tokens={c["name"]: c["value"] for c in ds["colors"]})
    except Exception as exc:  # noqa: BLE001
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium is not installed (python -m playwright install chromium)")
        raise
    res = CheckResult()
    browser.findings_from(rep, t, res)
    return rep, res


def _suite_for_html(tmp: Path, html: str, viewports: list[int], states: list[dict] | None = None,
                    tokens: dict[str, str] | None = None) -> CheckResult:
    tmp.mkdir(parents=True, exist_ok=True)
    entry = tmp / "prototype.html"
    entry.write_text(html)
    t = yaml.safe_load((PKG / "config" / "defaults.yaml").read_text())["thresholds"]["browser"]
    try:
        rep = browser.run_suite(entry, [], states or [], [{"id": "home", "route": ""}], viewports, t, tmp / "run",
                                tokens=tokens)
    except Exception as exc:  # noqa: BLE001
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium is not installed (python -m playwright install chromium)")
        raise
    res = CheckResult()
    browser.findings_from(rep, t, res)
    return res


def test_the_corrected_build_passes_every_browser_dimension(tmp_path):
    entry, man = _build(tmp_path, overlay=False)
    assert man["overlays"] == [] and entry.is_file()
    rep, res = _suite(entry, tmp_path / "run", [390, 768, 1440])
    failed = {d: o.evidence for d, o in res.dimensions.items() if not o.passed}
    assert not failed, failed
    assert len(rep["scenarios"]) == 4 * 3 and all(s["passed"] for s in rep["scenarios"])
    assert all(s["rendered"] for s in rep["states"])                 # loading, empty, error, storage-off, …
    assert rep["samples"].get("lot") and not rep["samples_dropped"], (rep["samples"], rep["samples_dropped"])  # W53
    assert not rep["axe"] and not rep["console"] and not rep["requests"]
    assert list((tmp_path / "run" / "screenshots").glob("*.png"))    # evidence a reviewer can open


def test_the_draft_overlay_fails_colour_contrast_on_the_queue(tmp_path):
    entry, man = _build(tmp_path, overlay=True)
    assert man["overlays"], "the draft declares its overlay"
    _, res = _suite(entry, tmp_path / "run-plan-v1", [1440], plan_attempt=1)   # the plan the draft was built to
    axe = res.dimensions["A11Y-AXE"]
    assert not axe.passed
    hit = [f for f in axe.findings if f["location"] == "queue:color-contrast"]
    assert hit and hit[0]["traced_node"] == "n11_prototype_development" and hit[0]["severity"] == "P2"
    assert res.dimensions["FUNC-SCENARIOS"].passed                   # it works; it is just not accessible


def test_the_reworked_plan_turns_the_layout_concern_into_a_check_the_draft_fails(tmp_path):
    entry, _ = _build(tmp_path, overlay=True)
    rep, res = _suite(entry, tmp_path / "run-plan-v2", [1440], plan_attempt=2)
    s01 = next(s for s in rep["scenarios"] if s["id"] == "S-01")
    assert not s01["passed"] and s01["failed_step"] == 7             # the comparison is not in view before deciding
    assert not res.dimensions["FUNC-SCENARIOS"].passed


def test_focus_obscured_2411_fails_when_a_focus_stop_is_wholly_under_a_sticky_bar(tmp_path):
    res = _suite_for_html(tmp_path, """<!doctype html>
<html><head><style>
body { margin: 0; font-family: sans-serif; }
.bar { position: fixed; inset: 0 0 auto 0; height: 84px; z-index: 10; background: #fff; }
.under { position: absolute; top: 24px; left: 24px; z-index: 1; }
</style></head><body>
<div class="bar">Sticky header</div>
<main data-screen="home"><a class="under" href="#next">Hidden focus target</a></main>
</body></html>""", [390])
    dim = res.dimensions["A11Y-FOCUS-VISIBLE-2411"]
    assert not dim.passed
    assert dim.findings and "home" in dim.findings[0]["message"] and "390" in dim.findings[0]["message"]


def test_focus_obscured_2411_passes_when_scroll_padding_keeps_focus_below_the_bar(tmp_path):
    res = _suite_for_html(tmp_path, """<!doctype html>
<html><head><style>
html { scroll-padding-top: 84px; }
body { margin: 0; font-family: sans-serif; }
.bar { position: fixed; inset: 0 0 auto 0; height: 84px; z-index: 10; background: #fff; }
main { padding-top: 120px; }
a { display: inline-block; margin: 12px; }
</style></head><body>
<div class="bar"><a href="#home">Header action</a></div>
<main data-screen="home"><a id="home" href="#ok">Visible focus target</a></main>
</body></html>""", [390])
    assert res.dimensions["A11Y-FOCUS-VISIBLE-2411"].passed


SHELL_2411 = """<!doctype html>
<html><head><style>
body { margin: 0; font-family: sans-serif; }
header { position: fixed; inset: 0 0 auto 0; height: 56px; z-index: 5; background: #fff; }
header button { width: 100%; height: 56px; }
#main { position: absolute; top: 56px; bottom: 0; left: 0; right: 0; overflow: auto; }
#main > a { display: block; height: 24px; margin-top: 10px; }
.region { height: 3000px; overflow: auto; margin: 16px; } .box { position: absolute; top: 300px; left: 0; width: 200px;
  height: 100px; overflow: auto; } .box a { display: block; height: 24px; margin-top: 300px; }
</style></head><body>
<header><button tabindex="-1">Search</button></header>
<main id="main" data-screen="home"><a id="strip" href="#a">Brand</a>
  <div style="overflow: hidden; height: 4px"><a style="position: absolute; top: 120px; left: 20px" href="#e">Escaped</a></div>
  <div class="region" tabindex="0" role="region" aria-label="Table">rows</div></main>
<script>
// an app that scrolls after focus moves: a strip of the brand link is left showing under the header
document.getElementById('strip').addEventListener('focus', () => setTimeout(() => { document.getElementById('main').scrollTop = 30; }, 0));
</script></body></html>"""


def test_focus_obscured_2411_reads_the_part_of_a_stop_that_is_shown(tmp_path):
    """Refresh field run: the three points were read across a stop's whole rect, so a scroll region taller than the
    viewport (its top in view) read as off-screen, and a link an app's scroller showed a strip of read as covered by the
    header above; neither is wholly hidden. The points are read in the part the viewport and its clipping boxes show, and
    in the part inside the viewport, so a link placed outside a small clipping box it escapes is not read as hidden."""
    res = _suite_for_html(tmp_path, SHELL_2411, [390])
    dim = res.dimensions["A11Y-FOCUS-VISIBLE-2411"]
    assert dim.passed, dim.findings


def test_focus_obscured_2411_names_the_container_a_stop_is_scrolled_out_of(tmp_path):
    """A stop scrolled out of a box mid-page is still inside the viewport: what lies at its place is not what covers it;
    the box that clips it is named."""
    html = SHELL_2411.replace('<main id="main" data-screen="home">', '<main id="main" data-screen="home"><div class="box" '
                              'id="box"><a id="gone" href="#g">Gone</a><div style="height:600px"></div></div>')
    html = html.replace("</script>", "document.getElementById('gone').addEventListener('focus', () => setTimeout(() => "
                        "{ document.getElementById('box').scrollTop = 400; }, 0));</script>")
    res = _suite_for_html(tmp_path, html, [390])
    dim = res.dimensions["A11Y-FOCUS-VISIBLE-2411"]
    msg = " ".join(f["message"] for f in dim.findings)
    assert not dim.passed and "Gone" in msg and "clipped by div#box" in msg and "covered by" not in msg, msg


def test_text_spacing_1412_fails_when_text_clips_after_spacing_is_applied(tmp_path):
    res = _suite_for_html(tmp_path, """<!doctype html>
<html><head><style>
body { font-family: sans-serif; margin: 32px; }
.title { width: 220px; height: 24px; overflow: hidden; line-height: 1.1; }
</style></head><body>
<main data-screen="home">
  <h1 class="title">A long row title that clips when the text spacing criterion is applied</h1>
</main></body></html>""", [1440])
    dim = res.dimensions["A11Y-TEXT-SPACING-1412"]
    assert not dim.passed
    assert dim.findings and "home" in dim.findings[0]["message"]


def test_text_spacing_1412_passes_when_text_can_wrap_freely(tmp_path):
    res = _suite_for_html(tmp_path, """<!doctype html>
<html><head><style>
body { font-family: sans-serif; margin: 32px; }
.title { max-width: 220px; overflow: visible; line-height: 1.1; }
</style></head><body>
<main data-screen="home">
  <h1 class="title">A long row title that wraps freely when the text spacing criterion is applied</h1>
</main></body></html>""", [1440])
    assert res.dimensions["A11Y-TEXT-SPACING-1412"].passed


def test_focus_obscured_2411_reads_a_smooth_scrolling_page_after_the_scroll_ends(tmp_path):
    """Independent audit #1: with `scroll-behavior: smooth`, the walk read each focus stop mid-scroll: 74 "wholly
    obscured" hits on a page where nothing covers anything, blocking defects no fix could clear."""
    links = "".join(f'<p><a href="#l{i}">Link {i}</a></p>' for i in range(40))
    res = _suite_for_html(tmp_path, f"""<!doctype html>
<html><head><style>html {{ scroll-behavior: smooth; }} body {{ margin: 0; font-family: sans-serif; }}
p {{ margin: 0 0 90px 16px; }}</style></head><body><main data-screen="home">{links}</main></body></html>""", [390])
    assert res.dimensions["A11Y-FOCUS-VISIBLE-2411"].passed, res.dimensions["A11Y-FOCUS-VISIBLE-2411"].evidence


def test_text_spacing_1412_ignores_clipping_that_is_there_before_the_spacing(tmp_path):
    """Independent audit #3: an ellipsis title and a decorative overflow clip with no spacing applied, so they are not a
    1.4.12 failure; only clipping the spacing causes, or makes worse, is."""
    res = _suite_for_html(tmp_path, """<!doctype html>
<html><head><style>
body { font-family: sans-serif; margin: 32px; }
.one { width: 160px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style></head><body>
<main data-screen="home"><p class="one">A single-line title with an ellipsis by design, long enough to clip</p></main>
</body></html>""", [1440])
    assert res.dimensions["A11Y-TEXT-SPACING-1412"].passed, res.dimensions["A11Y-TEXT-SPACING-1412"].evidence


# ------------------------------------------------------------------------------------------------ config batch 2
_PANEL = """<!doctype html><html lang="en"><head><title>t</title><style>:root{--ink:#1A1A1A;--paper:#FFFFFF}
body{color:var(--ink);background:var(--paper);font:16px sans-serif} button{font:inherit;padding:8px 16px}</style></head>
<body><main data-screen="home"><h1>Lots</h1><div id="host"></div></main><script>
const host = document.getElementById('host');
function panel() { host.innerHTML = '<div data-state="empty" role="alert"><p>No lots match</p>' +
  '<button id="clear">Clear filters</button></div>'; }
panel(); %s
</script></body></html>"""


def test_a_state_rebuilt_four_times_a_second_does_not_hold_still(tmp_path):
    """B-09 (field run 2, R2-12): an alert panel rebuilt every 250 ms passed FUNC-STATES 80 of 80; focus on its button
    was lost within a second and every rebuild re-announced it."""
    states = [{"screen": "home", "state": "empty", "route": "", "marker": '[data-state="empty"]'}]
    res = _suite_for_html(tmp_path, _PANEL % "setInterval(panel, 250);", [1024], states)
    o = res.dimensions["FUNC-STATES"]
    assert not o.passed and "do not hold still" in o.evidence and "was lost" in o.evidence, o.evidence
    ok = _suite_for_html(tmp_path / "still", _PANEL % "", [1024], states)
    assert ok.dimensions["FUNC-STATES"].passed, ok.dimensions["FUNC-STATES"].evidence


def test_a_way_back_that_does_nothing_fails_and_one_that_works_passes(tmp_path):
    """B-09 (R2-12): a "Clear filters" with no handler passed; the plan's `recover` presses it and expects the state gone."""
    states = [{"screen": "home", "state": "empty", "route": "", "marker": '[data-state="empty"]',
               "recover": {"click": "#clear"}}]
    dead = _suite_for_html(tmp_path, _PANEL % "", [1024], states)
    o = dead.dimensions["FUNC-STATES"]
    assert not o.passed and "ways back that do nothing" in o.evidence and "#clear" in o.evidence, o.evidence
    live = _suite_for_html(tmp_path / "live", _PANEL % "document.getElementById('clear').onclick = () => { host.innerHTML "
                           "= '<p>12 lots</p>'; };", [1024], states)
    assert live.dimensions["FUNC-STATES"].passed, live.dimensions["FUNC-STATES"].evidence


_TOKENS = """<!doctype html><html lang="en"><head><title>t</title><style>:root{--ink:#1A1A1A;--paper:#FFFFFF;%s}
body{color:var(--ink);background:var(--paper);font:16px sans-serif}
.btn{background:var(--red-ink);color:var(--paper);padding:8px 16px;border:0} .ok{border-color:var(--gone, var(--also-gone))}</style></head>
<body><main data-screen="home"><h1>Lots</h1><button class="btn ok">Release</button></main></body></html>"""


def test_a_token_defined_as_itself_is_undefined_where_it_is_used(tmp_path):
    """B-08 (R2-09): `--red-ink: var(--red-ink)` is undefined at runtime, so the button lost its fill while every gate
    passed. A token with a fallback (`var(--gone, var(--also-gone))`) is fine, whatever the fallback holds."""
    bad = _suite_for_html(tmp_path, _TOKENS % "--red-ink:var(--red-ink)", [1024])
    o = bad.dimensions["VIS-TOKENS-RUNTIME"]
    assert not o.passed and "--red-ink (:root, .btn" in o.evidence and "gone" not in o.evidence, o.evidence
    good = _suite_for_html(tmp_path / "good", _TOKENS % "--red-ink:#B42318", [1024])
    assert good.dimensions["VIS-TOKENS-RUNTIME"].passed, good.dimensions["VIS-TOKENS-RUNTIME"].evidence


def test_a_design_system_colour_the_page_redefines_differs_in_any_spelling_only_when_it_really_differs(tmp_path):
    """B-08: each design-system colour the page defines at :root must compute to the system's value; another spelling
    of the same colour is the same colour."""
    html = _TOKENS % "--red-ink:rgb(180 35 24)"
    same = _suite_for_html(tmp_path, html, [1024], tokens={"red-ink": "#B42318", "ink": "#1a1a1a"})
    assert same.dimensions["VIS-TOKENS-RUNTIME"].passed, same.dimensions["VIS-TOKENS-RUNTIME"].evidence
    off = _suite_for_html(tmp_path / "off", html, [1024], tokens={"red-ink": "#C0392B", "ink": "#1A1A1A"})
    o = off.dimensions["VIS-TOKENS-RUNTIME"]
    assert not o.passed and "red-ink = rgb(180 35 24) (system #C0392B)" in o.evidence, o.evidence


# ------------------------------------------------------------------------------------------------ config batch 2 review
_HEAD = """<!doctype html><html lang="en"><head><title>t</title><style>:root{--ink:#1A1A1A;--paper:#FFFFFF}
body{color:var(--ink);background:var(--paper);font:16px sans-serif} %s</style></head>
<body><main data-screen="home"><h1>Lots</h1>%s</main>%s</body></html>"""


def _tok(tmp, css, body, tail="", tokens=None, states=None):
    return _suite_for_html(tmp, _HEAD % (css, body, tail), [1024], states, tokens).dimensions["VIS-TOKENS-RUNTIME"]


def test_valid_css_that_reads_empty_is_not_an_undefined_token(tmp_path):
    """Review C1: Tailwind's `--tw-ring-inset: ;` is empty on purpose; a property on ::before/::after lives there, not
    on the host; a rule in a media query that does not apply is not judged. Each was a P1 "define --x"."""
    tailwind = ("*,::before,::after{--tw-ring-inset: ;--tw-ring-offset-width:0px;--tw-ring-offset-color:#fff;"
                "--tw-ring-color:rgb(59 130 246/.5);--tw-ordinal: ;--tw-numeric-figure: ;--tw-content:''}"
                ".ring-1{--tw-ring-shadow:var(--tw-ring-inset) 0 0 0 calc(1px + var(--tw-ring-offset-width)) "
                "var(--tw-ring-color);box-shadow:var(--tw-ring-shadow)}"
                ".tabular-nums{font-variant-numeric:var(--tw-ordinal) var(--tw-numeric-figure)}"
                ".old{--tw-legacy:var(--tw-empty,/*!*/ /*!*/);border-width:var(--tw-legacy)}"
                ".after\\\\:absolute::after{content:var(--tw-content);position:absolute}"
                ".chip::before{--dot:var(--ink);content:'';display:inline-block;width:8px;height:8px;background:var(--dot)}"
                "@media (max-width:600px){:root{--rail:#1A1A1A} nav{border-left:4px solid var(--rail)}}"
                "@media print{:root{--print-ink:#000} main{color:var(--print-ink)}}")
    o = _tok(tmp_path, tailwind, '<div class="ring-1 tabular-nums old">12</div><span class="chip after:absolute">Hold'
                                 '</span><nav>n</nav>')
    assert o.passed, o.evidence


def test_nested_css_shadow_dom_and_a_linked_sheet_are_all_read(tmp_path):
    """Review I1: nested rules, shadow roots and a file:// stylesheet were never read, and the check said every token
    resolves."""
    nested = _tok(tmp_path / "n", ".card{padding:8px; & .btn{background:var(--brand-fill)}}",
                  '<div class="card"><button class="btn">Release</button></div>')
    assert not nested.passed and "--brand-fill" in nested.evidence, nested.evidence
    shadow = _tok(tmp_path / "s", "", "<x-btn></x-btn>", "<script>customElements.define('x-btn', class extends HTMLElement "
                  "{ constructor(){ super(); this.attachShadow({mode:'open'}).innerHTML = '<style>button{background:"
                  "var(--shadow-fill)}</style><button>Release</button>'; }});</script>")
    assert not shadow.passed and "--shadow-fill" in shadow.evidence, shadow.evidence
    linked = tmp_path / "l"
    linked.mkdir()
    (linked / "s.css").write_text(".btn{background:var(--linked-fill)}")
    html = (_HEAD % ("", '<button class="btn">Release</button>', "")).replace("</head>", '<link rel="stylesheet" '
                                                                               'href="s.css"></head>')
    o = _suite_for_html(linked, html, [1024]).dimensions["VIS-TOKENS-RUNTIME"]
    assert not o.passed and "--linked-fill" in o.evidence and "could not be read" not in o.evidence, o.evidence


def test_layers_supports_inline_styles_fallbacks_and_registered_properties(tmp_path):
    """Kept from the review: @layer and @supports are read, inline styles too, a fallback is not a use, and an
    @property initial value defines the token."""
    o = _tok(tmp_path, "@layer base{@supports (display:grid){.btn{background:var(--nope-a)}}} .ok{color:var(--x, var(--y))}",
             '<button class="btn ok">R</button><div style="border-color:var(--nope-b)">x</div>')
    assert not o.passed and "--nope-a" in o.evidence and "--nope-b" in o.evidence and "--y" not in o.evidence, o.evidence
    ok = _tok(tmp_path / "p", "@property --brand{syntax:'<color>';inherits:true;initial-value:#B42318} "
              ".btn{background:var(--brand)}", '<button class="btn">R</button>')
    assert ok.passed, ok.evidence


def test_a_token_used_only_in_a_planned_state_is_read_there(tmp_path):
    """Review I1: tokens were read on screen routes only, so an alert fill used only in an error state went unchecked."""
    tail = ("<script>if (location.search.includes('s=err')) document.querySelector('main').insertAdjacentHTML('beforeend', "
            "'<div data-state=\"error\" class=\"alert\">The list did not load</div>');</script>")
    states = [{"screen": "home", "state": "error", "route": "?s=err", "marker": '[data-state="error"]'}]
    o = _tok(tmp_path, ".alert{background:var(--alert-fill)}", "", tail, states=states)
    assert not o.passed and "--alert-fill" in o.evidence, o.evidence


def test_a_design_system_colour_is_compared_as_the_browser_resolves_it(tmp_path):
    """Review S5: a named colour was skipped; the browser now resolves each token before it is compared."""
    same = _tok(tmp_path, "", "<p>x</p>", tokens={"ink": "#1A1A1A", "paper": "white"})
    assert same.passed, same.evidence
    off = _tok(tmp_path / "o", "", "<p>x</p>", tokens={"ink": "#1A1A1A", "paper": "ivory"})
    assert not off.passed and "paper = #FFFFFF (system ivory)" in off.evidence, off.evidence


_APP = """<!doctype html><html lang="en"><head><title>t</title><style>body{font:16px sans-serif} button{padding:8px 16px}
</style></head><body><div id="app"></div><script>%s</script></body></html>"""
_EMPTY = [{"screen": "home", "state": "empty", "route": "", "marker": '[data-state="empty"]'}]


def _states(tmp, js, states=None):
    import json as _json
    res = _suite_for_html(tmp, _APP % js, [1024], states or _EMPTY)
    return res.dimensions["FUNC-STATES"], _json.loads((tmp / "run" / "browser-report.json").read_text())["states"]


def test_a_panel_rebuilt_four_times_a_second_fails_on_its_changes_alone(tmp_path):
    """Review I2: only top-level nodes were counted, so a rebuilt panel with no control made 8 "changes" and passed."""
    js = ("const app = document.getElementById('app'); function r(){ app.innerHTML = '<main data-screen=\"home\"><h1>Lots</h1>"
          "<div data-state=\"empty\"><p>No lots match</p></div></main>'; } r(); setInterval(r, 250);")
    o, rows = _states(tmp_path, js)
    assert not o.passed and "elements added or removed" in o.evidence and rows[0]["watch"]["changes"] > 10, o.evidence


def test_a_playwright_marker_a_busy_loading_state_and_a_resize_rerender_do_not_fail(tmp_path):
    """Review I3, S3: a `:visible` marker the render check accepts could not be watched; a held loading state updating
    its text failed. And a still state in an app that re-renders on resize passes (a hypothesis the review rejected)."""
    still = ("document.getElementById('app').innerHTML = '<main data-screen=\"home\"><h1>Lots</h1>"
             "<div data-state=\"empty\"><p>No lots match</p><button>Clear filters</button></div></main>';")
    o, _ = _states(tmp_path / "v", still, [{**_EMPTY[0], "marker": '[data-state="empty"]:visible'}])
    assert o.passed, o.evidence
    busy = ("document.getElementById('app').innerHTML = '<main data-screen=\"home\"><h1>Lots</h1><div data-state=\"empty\" "
            "aria-busy=\"true\"><span id=\"p\">Loading</span><i></i></div></main>'; let n = 0; setInterval(() => { "
            "document.getElementById('p').innerHTML = '<b>Loading</b>' + '.'.repeat(n++ % 4); }, 80);")
    o, _ = _states(tmp_path / "b", busy)
    assert o.passed, o.evidence
    resize = ("const app = document.getElementById('app'); function render(){ app.innerHTML = '<main data-screen=\"home\">"
              "<h1>Lots</h1><div data-state=\"empty\"><p>No lots match</p><button>Clear filters</button></div></main>'; } "
              "let t; addEventListener('resize', () => { clearTimeout(t); t = setTimeout(render, 200); }); render();")
    o, _ = _states(tmp_path / "r", resize)
    assert o.passed, o.evidence


def test_a_way_back_is_judged_on_its_own_state(tmp_path):
    """Review S2: a way back to another screen that also has an empty state failed, and a working toolbar copy could
    stand in for a dead button in the panel."""
    nav = ("const app = document.getElementById('app'); function show(){ app.innerHTML = location.hash === '#/b' ? "
           "'<main data-screen=\"b\"><h1>B</h1><div data-state=\"empty\"><p>Nothing yet</p></div></main>' : "
           "'<main data-screen=\"home\"><h1>Lots</h1><div data-state=\"empty\"><p>No lots</p><a href=\"#/b\">Go to B</a>"
           "</div></main>'; } addEventListener('hashchange', show); show();")
    o, rows = _states(tmp_path / "n", nav, [{**_EMPTY[0], "recover": {"click": "a"}}])
    assert o.passed and rows[0]["recovered"]["ok"], (o.evidence, rows)
    dead = ("const app = document.getElementById('app'); app.innerHTML = '<main data-screen=\"home\"><h1>Lots</h1>"
            "<div class=\"toolbar\"><button class=\"clear\" id=\"tb\">Clear filters</button></div><div data-state=\"empty\">"
            "<p>No lots</p><button class=\"clear\">Clear filters</button></div></main>'; document.getElementById('tb')"
            ".addEventListener('click', () => document.querySelector('[data-state]').remove());")
    o, rows = _states(tmp_path / "d", dead, [{**_EMPTY[0], "recover": {"click": ".clear"}}])
    assert not o.passed and rows[0]["recovered"]["ok"] is False and "ways back that do nothing" in o.evidence, rows


def test_a_page_that_leaves_while_watched_fails_and_an_unfocused_state_is_named(tmp_path):
    """Review S2, S4: a state whose page navigated during the watch passed silently; a state with no control to focus
    passed with nothing saying focus was never watched."""
    leave = ("document.getElementById('app').innerHTML = '<main data-screen=\"home\"><h1>Lots</h1><div data-state=\"empty\">"
             "<p>No lots</p></div></main>'; setTimeout(() => { location.hash = '#/elsewhere'; }, 300);")
    o, _ = _states(tmp_path / "l", leave)
    assert not o.passed and "navigated away" in o.evidence, o.evidence
    still = ("document.getElementById('app').innerHTML = '<main data-screen=\"home\"><h1>Lots</h1><div data-state=\"empty\">"
             "<p>No lots</p></div></main>';")
    o, _ = _states(tmp_path / "s", still)
    assert o.passed and "no control to focus, so focus was not watched, in 1 state(s): home#empty@1024" in o.evidence, o.evidence


def test_a_token_check_that_breaks_is_reported_as_unmeasured_and_the_suite_still_runs(tmp_path, monkeypatch):
    """Review S1: an exception in the token read escaped to `check()`, which lost every browser dimension."""
    monkeypatch.setattr(browser, "JS_TOKENS", "() => { throw new Error('boom'); }")
    res = _suite_for_html(tmp_path, _HEAD % ("", "<p>x</p>", ""), [1024])
    o = res.dimensions["VIS-TOKENS-RUNTIME"]
    assert not o.passed and "not measured" in o.evidence and "boom" in o.evidence, o.evidence
    assert res.dimensions["FUNC-STATES"].passed and "A11Y-AXE" in res.dimensions


def test_a_universal_rule_with_pseudo_elements_is_judged_and_a_container_rule_is_named_once(tmp_path):
    """On the first project's build, `*, ::before, ::after` lost its list items when the pseudo-elements were stripped,
    so the browser rejected it, and a @container group was counted once per page (161 "rules not judged" for 8)."""
    css = ("*, ::before, ::after{--tw-lost: var(--tw-lost)} .x{border-color: var(--tw-lost)} "
           "@container (min-width: 10px){.y{color: var(--inside)}}")
    states = [{"screen": "home", "state": "empty", "route": "", "marker": "h1"}]
    o = _tok(tmp_path, css, '<p class="x">x</p><p class="y">y</p>', states=states)
    assert not o.passed and "--tw-lost" in o.evidence and "rejects" not in o.evidence, o.evidence
    assert "not judged: 1 @container group(s)" in o.evidence, o.evidence


# ------------------------------------------------------------------------------------------------ N-28 reference parity
def _ref_pair(tmp: Path) -> tuple[Path, Path]:
    """The example build as its own reference, and a copy with the three regressions field run 2 found (R2-21)."""
    ref, _ = _build(tmp / "ref", overlay=False)
    src = tmp / "src-reg"
    shutil.copytree(EXAMPLE / "prototype", src)
    with (src / "src" / "styles.css").open("a") as f:
        f.write("\nh1 { font-size: 28px !important; font-weight: 600 !important; }\n#search { display: none !important; }\n"
                "@media (max-width: 639px) { .queue-table { display: table !important; } .queue-table tbody { display: table-row-group !important; } .queue-table tr { display: table-row !important; } .queue-table td { display: table-cell !important; } }\n")
    out = tmp / "reg"
    subprocess.run([sys.executable, str(src / "build.py"), "--src", str(src), "--out", str(out)], check=True,
                   capture_output=True, text=True)
    return ref, out / json.loads((out / "build-manifest.json").read_text())["entry"]


def _parity_suite(entry: Path, reference: Path | None, out: Path, screens: list[dict] | None = None,
                  routes: dict | None = None, expected: list | None = None, widths: tuple = (390, 1440)):
    exp = json.loads((FIX / "n07_experience_architecture" / "attempt-1" / "experience.json").read_text())
    screens = screens or [{"id": s["id"], "route": s["route"]} for s in exp["screens"] if s["id"] in ("queue", "lot")]
    t = yaml.safe_load((PKG / "config" / "defaults.yaml").read_text())["thresholds"]["browser"]
    try:
        rep = browser.run_suite(entry, [], [], screens, list(widths), t, out,
                                reference={"entry": str(reference), "routes": routes or {}, "expected": expected or []}
                                if reference else None)
    except Exception as exc:  # noqa: BLE001
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium is not installed (python -m playwright install chromium)")
        raise
    res = CheckResult()
    browser.findings_from(rep, t, res)
    return rep, res


def test_a_refresh_that_drops_the_search_resizes_titles_and_loses_the_card_layout_is_flagged(tmp_path):
    """N-28 (field run 2, R2-21): a merge dropped the header search, a stylesheet leak resized titles, and a phone table
    stopped becoming cards; all 15 browser dimensions passed. REF-PARITY names each drift with both values, and the
    reference's pages count toward none of the build's own findings."""
    ref, reg = _ref_pair(tmp_path)
    rep, res = _parity_suite(reg, ref, tmp_path / "run")
    o = res.dimensions["REF-PARITY"]
    assert not o.passed, o.evidence
    assert "queue@390: title 28 px/600 (reference 24 px/700)" in o.evidence, o.evidence
    assert "queue@1440: no search control (the reference has one)" in o.evidence, o.evidence
    assert "queue@390: tables shown as table (reference: cards)" in o.evidence, o.evidence
    assert "queue@1440: tables shown as" not in o.evidence
    assert not rep["requests"] and not rep["console"]
    same, res2 = _parity_suite(ref, ref, tmp_path / "same")
    assert res2.dimensions["REF-PARITY"].passed and "no unexplained drift" in res2.dimensions["REF-PARITY"].evidence
    _, res3 = _parity_suite(ref, None, tmp_path / "none")
    assert res3.dimensions["REF-PARITY"].passed and "no reference build declared" in res3.dimensions["REF-PARITY"].evidence


def test_a_declared_reference_that_is_missing_fails_parity_only():
    """N-28: a reference that `pdg.project.yaml` names but that is not on disk is an error on REF-PARITY, never a pass,
    and never the whole suite."""
    from types import SimpleNamespace
    ctx = SimpleNamespace(engine=SimpleNamespace(project=SimpleNamespace(root=PKG, config={"reference": {"entry": "nope.html"}})))
    with pytest.raises(FileNotFoundError, match="nope.html"):
        browser._reference(ctx)
    rep = {"reference": None, "reference_error": "the reference build's entry nope.html does not exist", "scenarios": [],
           "states": [], "screens": [], "axe": [], "reflow_320": [], "reduced_motion": [], "console": [], "requests": [],
           "timing_ms": [], "forbidden_text": [], "tokens": [], "parity": []}
    t = yaml.safe_load((PKG / "config" / "defaults.yaml").read_text())["thresholds"]["browser"]
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert not res.dimensions["REF-PARITY"].passed and "nope.html" in res.dimensions["REF-PARITY"].evidence
    assert res.dimensions["FUNC-CONSOLE"].passed


def test_table_mode_is_read_from_the_rows_not_the_table_element(tmp_path):
    """N-28: a card layout often keeps `<table>` as a table and restacks only its rows (grid or block rows). Reading
    the table element alone would call those cards a table."""
    page_html = ("<!doctype html><html><head><style>table{display:table} .cards tr{display:grid}</style></head><body>"
                 "<h1>t</h1><table class='%s'><tbody><tr><td>a</td><td>b</td></tr></tbody></table></body></html>")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            modes = []
            for cls in ("cards", "plain"):
                f = tmp_path / f"{cls}.html"
                f.write_text(page_html % cls)
                pg = b.new_page()
                pg.goto(f.as_uri())
                modes.append(pg.evaluate(browser.JS_PARITY)["table_mode"])
            b.close()
    except Exception as exc:  # noqa: BLE001
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium is not installed (python -m playwright install chromium)")
        raise
    assert modes == ["cards", "table"], modes


def test_parity_expected_differences_skipped_screens_and_a_sandbox_that_treats_both_sides_alike(tmp_path):
    """N-28 review I1, I3 and the second run's lesson 3: an intended drift listed in `reference.expected` with its
    reason is shown, not failed; a screen the reference does not render, or routed to null, is skipped and named; and a
    remote stylesheet is blocked on both sides, so an identical file never drifts from itself."""
    ref, reg = _ref_pair(tmp_path)
    _, res = _parity_suite(reg, ref, tmp_path / "e", expected=[
        {"property": "title", "reason": "the refresh adopts the new title scale"},
        {"property": "search", "screen": "queue", "reason": "search moves to the global header"},
        {"property": "tables", "reason": "the queue stays a table on phones"}])
    o = res.dimensions["REF-PARITY"]
    assert o.passed and "intended: the refresh adopts the new title scale" in o.evidence, o.evidence
    screens = [{"id": "queue", "route": "#/queue"}, {"id": "brand-new", "route": "#/queue"}, {"id": "lot", "route": "#/lot/L-2418"}]
    _, res = _parity_suite(ref, ref, tmp_path / "s", screens=screens, routes={"lot": None}, widths=(1440,))
    o = res.dimensions["REF-PARITY"]
    assert o.passed and "brand-new@1440 (the reference does not render this screen" in o.evidence, o.evidence
    assert "lot@1440 (its route is null" in o.evidence, o.evidence
    site = tmp_path / "cdn"
    site.mkdir()
    (site / "p.html").write_text('<!doctype html><html><head><link rel="stylesheet" href="http://127.0.0.1:9/f.css">'
                                 '<style>h1{font-size:24px}</style></head><body><main data-screen="home"><h1>Home</h1>'
                                 '</main></body></html>')
    rep, res = _parity_suite(site / "p.html", site / "p.html", tmp_path / "c", screens=[{"id": "home", "route": ""}],
                             widths=(390,))
    o = res.dimensions["REF-PARITY"]
    assert o.passed and "blocked on both sides alike" in o.evidence and "'build@390': 1" in o.evidence, o.evidence


def test_parity_heuristics_ignore_a_hidden_title_radios_and_padding(tmp_path):
    """N-28 review S1: a visually hidden h1 was read as the title, radios pulled the control-height median down, and a
    padded title counted as two lines."""
    base = ("<!doctype html><html><head><style>.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);"
            "font-size:12px} h1{font-size:24px;line-height:30px} button{height:40px}%s</style></head><body>"
            "<main data-screen='home'>%s<h1>Queue</h1><button>Go</button><button>Stop</button>%s</main></body></html>")
    a, b = tmp_path / "a.html", tmp_path / "b.html"
    a.write_text(base % ("", "", ""))
    b.write_text(base % ("h1{padding:16px 0}", "<h1 class='sr'>Skip to content</h1>",
                         "<input type='radio' name='s'><input type='radio' name='s'><input type='radio' name='s'>"))
    _, res = _parity_suite(b, a, tmp_path / "h", screens=[{"id": "home", "route": ""}], widths=(1440,))
    o = res.dimensions["REF-PARITY"]
    assert o.passed, o.evidence


# ------------------------------------------------------------------------------------------------ W47 width band
_BAND_PAGE = """<!doctype html><html lang="en"><head><title>t</title><style>body{margin:0;font:16px sans-serif}
.tile{width:220px;background:#eee;overflow-wrap:anywhere} .tag{display:inline-block;background:#dde;white-space:nowrap;width:auto}
@media (min-width:1200px) and (max-width:1260px){ .tile{width:48px} .tagbox{width:40px;background:#eef} }
@media (min-width:1300px) and (max-width:1320px){ .wide{width:1500px;height:8px} }
.soft{width:48px;background:#eee;overflow-wrap:anywhere} .hy{width:48px;hyphens:auto;overflow-wrap:anywhere}
</style></head><body><main data-screen="home"><h1>Home</h1><div class="tile">contaminants</div>
<div class="tagbox"><span class="tag">Microbiology</span></div><div class="wide"></div>
<div class="soft">conta&shy;minants</div><div class="hy" lang="en">contaminants</div>
<div style="overflow-x:auto;width:300px"><table style="width:900px"><tr style="background:#f5f5f5"><td>Lot</td><td>Supplier
</td></tr></table></div></main></body></html>"""


def test_a_failure_between_the_planned_widths_is_found_and_named_by_its_width_range(tmp_path):
    """Field run W47: Wei found a word split mid-word and a tag past its tile at 1200-1260 px on a build every fixed-width
    check had passed (planned widths 1024 and 1440). The band catches it and names the range; an allowed break (a soft
    hyphen, hyphens: auto) is not one."""
    res = _suite_for_html(tmp_path, _BAND_PAGE, [1024, 1440])
    band, text = res.dimensions["RESP-BAND"], res.dimensions["RESP-TEXT"]
    assert not band.passed and "home at 1304 px" in band.evidence, band.evidence   # the band samples 1024 + 20k
    assert not text.passed and "'contaminants' in div.tile at 1204–1244 px" in text.evidence, text.evidence
    assert "div.tagbox at 1204–1244 px" in text.evidence, text.evidence
    assert "div.soft" not in text.evidence and "div.hy" not in text.evidence, text.evidence
    assert " tr " not in text.evidence and "table" not in text.evidence, text.evidence   # it scrolls in its own region
    assert res.dimensions["RESP-OVERFLOW"].passed          # the fixed widths saw nothing


def test_the_band_spans_the_planned_widths_and_a_calm_page_passes(tmp_path):
    from pdg.tools.browser import band_widths
    assert band_widths([390, 768, 1440], 20)[:2] == [390, 410] and band_widths([390, 1440], 20)[-1] == 1440
    thin = band_widths([320, 1920], 5, cap=80)
    assert len(thin) == 80 and (thin[0], thin[-1]) == (320, 1920) and band_widths([1024], 20) == [1024]
    calm = _BAND_PAGE.replace("@media (min-width:1200px)", "@media (min-width:9000px)").replace(
        "@media (min-width:1300px)", "@media (min-width:9100px)")
    res = _suite_for_html(tmp_path, calm, [1024, 1440])
    assert res.dimensions["RESP-BAND"].passed and res.dimensions["RESP-TEXT"].passed, (
        res.dimensions["RESP-BAND"].evidence, res.dimensions["RESP-TEXT"].evidence)


def _band(tmp, body: str, style: str = "", viewports=(1024, 1440)):
    html = (f"<!doctype html><html lang='en'><head><title>t</title><style>body{{margin:0;font:16px sans-serif}}{style}"
            f"</style></head><body><main data-screen='home'><h1>Home</h1>{body}</main></body></html>")
    return _suite_for_html(tmp, html, list(viewports))


def test_a_layout_sized_at_load_or_by_a_late_resize_is_judged_on_a_fresh_load(tmp_path):
    """W47 review I1: resizing one page from the widest width down, a chart sized once at load and a 250 ms debounced
    resize handler both overflowed every narrower width, though a user loading the page there sees none."""
    at_load = ("<div id='c' style='height:10px;background:#ccc'></div><script>document.getElementById('c').style.width = "
               "innerWidth + 'px'</script>")
    res = _band(tmp_path / "a", at_load)
    assert res.dimensions["RESP-BAND"].passed and "clear on a fresh load" in res.dimensions["RESP-BAND"].evidence, (
        res.dimensions["RESP-BAND"].evidence)
    late = ("<div id='c' style='height:10px;background:#ccc'></div><script>const c = document.getElementById('c'); "
            "const fit = () => { c.style.width = innerWidth + 'px'; }; fit(); let t; addEventListener('resize', () => "
            "{ clearTimeout(t); t = setTimeout(fit, 250); });</script>")
    assert _band(tmp_path / "b", late).dimensions["RESP-BAND"].passed


def test_band_exclusions_hold_only_where_they_are_true(tmp_path):
    """W47 review I2, I4: a region that really scrolls sideways holds its content, but an app shell whose main column
    only scrolls vertically does not hide a tag running past its tile; a table cell is still a box."""
    wide_rows = ("<div style='overflow-x:auto;width:300px'><div class='row' style='background:#f5f5f5'>"
                 "<span style='display:inline-block;white-space:nowrap;min-width:900px'>Lot 2418 Northwind Metals released"
                 "</span></div></div>")   # a row narrower than its content, in a region that scrolls sideways
    res = _band(tmp_path / "s", wide_rows)
    assert res.dimensions["RESP-TEXT"].passed, res.dimensions["RESP-TEXT"].evidence
    shell = ("<div style='display:flex;height:400px'><nav style='width:200px'>nav</nav><div style='overflow-y:auto;flex:1'>"
             "<div class='tile' style='width:80px;background:#eee'><span style='white-space:nowrap'>Microbiology</span>"
             "</div></div></div>")
    res = _band(tmp_path / "h", shell)
    assert not res.dimensions["RESP-TEXT"].passed and "div.tile" in res.dimensions["RESP-TEXT"].evidence, (
        res.dimensions["RESP-TEXT"].evidence)
    cell = ("<table style='table-layout:fixed;width:200px'><tr><td class='hm' style='width:60px;background:#fee'>"
            "<span style='white-space:nowrap'>Microbiology</span></td><td>x</td></tr></table>")
    res = _band(tmp_path / "c", cell)
    assert not res.dimensions["RESP-TEXT"].passed and "td.hm" in res.dimensions["RESP-TEXT"].evidence, (
        res.dimensions["RESP-TEXT"].evidence)


def test_band_ignores_text_that_wraps_by_design_and_content_placed_on_purpose(tmp_path):
    """W47 review I3: Chinese text wraps between characters, screen-reader-only text is not seen, a floated drop cap sits
    beside its word, and an absolute badge, an invisible tooltip or a full-bleed negative margin is placed there on
    purpose. None is a finding. A gradient tile is still a box (S2)."""
    body = ("<p style='width:120px'>汚染物質の検査結果は基準値の範囲内でした汚染物質の検査結果</p>"
            "<span style='position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);overflow-wrap:break-word'>"
            "Dismissnotifications</span>"
            "<p class='dc' style='width:300px'>Contaminants were within specification across every lot.</p>"
            "<div class='card' style='position:relative;width:120px;background:#eee'>Card<span style='position:absolute;"
            "right:-10px;top:0'>NEW</span><span style='opacity:0;display:inline-block;width:400px'>tooltip text</span>"
            "<div style='margin:0 -40px'>Full bleed band</div></div>")
    res = _band(tmp_path / "f", body, ".dc::first-letter{float:left;font-size:48px;line-height:1}")
    assert res.dimensions["RESP-TEXT"].passed, res.dimensions["RESP-TEXT"].evidence
    grad = "<div class='g' style='width:60px;background:linear-gradient(#fff,#eee)'><span style='white-space:nowrap'>Microbiology</span></div>"
    res = _band(tmp_path / "g", grad)
    assert not res.dimensions["RESP-TEXT"].passed and "div.g" in res.dimensions["RESP-TEXT"].evidence


def test_a_band_that_is_not_swept_is_not_a_pass():
    """W47 review S4: `band_step_px: 0` passed the MUST with nothing swept."""
    rep = {"band": [], "band_step": 0, "parity": [], "reference": None, "states": [], "tokens": [], "scenarios": [],
           "screens": [], "axe": [], "reflow_320": [], "reduced_motion": [], "console": [], "requests": [], "timing_ms": [],
           "forbidden_text": []}
    t = yaml.safe_load((PKG / "config" / "defaults.yaml").read_text())["thresholds"]["browser"]
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert not res.dimensions["RESP-BAND"].passed and "not measured" in res.dimensions["RESP-BAND"].evidence


def test_a_hidden_header_row_and_a_scrolling_tab_strip_do_not_spill(tmp_path):
    """On the first run's v9, a visually hidden header row (a 1 px clipped thead with a background) and a card whose tab
    strip scrolls sideways inside it read as text past its box on three screens. Neither shows anything past a box."""
    body = ("<table><thead style='position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)'>"
            "<tr style='display:block;background:#fff;border:1px solid #ccc'><th>Notice</th><th>Market</th><th>Topic</th></tr>"
            "</thead><tbody><tr><td>x</td></tr></tbody></table>"
            "<div class='card' style='width:240px;background:#fff;border:1px solid #ccc'><div style='overflow-x:auto;"
            "white-space:nowrap'><button>Archived 1</button><button>All 21</button><button>Regulatory 12</button>"
            "<button>Scientific 9</button></div></div>")
    res = _band(tmp_path, body)
    assert res.dimensions["RESP-TEXT"].passed, res.dimensions["RESP-TEXT"].evidence

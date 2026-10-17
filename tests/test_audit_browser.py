from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from pdg.artifacts import PrototypePlan
from pdg.context import CheckResult
from pdg.tools import browser

from .conftest import PKG

pytest.importorskip("playwright")


def _thresholds() -> dict:
    return yaml.safe_load((PKG / "config" / "defaults.yaml").read_text())["thresholds"]["browser"]


def _write_html(path: Path, body: str, head: str = "") -> Path:
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Audit fixture</title>
  {head}
</head>
<body>
  {body}
</body>
</html>
""",
        encoding="utf-8",
    )
    return path


def _run(entry: Path, out: Path, *, scenarios=None, screens=None) -> tuple[dict, CheckResult]:
    t = _thresholds()
    try:
        rep = browser.run_suite(
            entry,
            scenarios or [],
            [],
            screens or [{"id": "one", "route": ""}],
            [390],
            t,
            out,
        )
    except Exception as exc:  # noqa: BLE001
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium is not installed (python -m playwright install chromium)")
        raise
    res = CheckResult()
    browser.findings_from(rep, t, res)
    return rep, res


def test_a11y_focus_distinguishes_duplicate_labelled_tab_stops(tmp_path):
    entry = _write_html(
        tmp_path / "duplicate-buttons.html",
        """
<main>
  <h1>Duplicate controls</h1>
  <button>View</button>
  <button>View</button>
  <button id="release" class="bad">Release</button>
</main>
""",
        """
<style>
  body { font-family: system-ui, sans-serif; color: #111; background: #fff; }
  button { min-width: 80px; min-height: 44px; margin: 16px; }
  button:focus { outline: 3px solid #005fcc; outline-offset: 2px; }
  button.bad:focus { outline: none; box-shadow: none; }
</style>
""",
    )

    _, res = _run(entry, tmp_path / "out")

    assert not res.dimensions["A11Y-FOCUS"].passed
    assert "Release" in json.dumps(res.dimensions["A11Y-FOCUS"].findings)


def test_a11y_focus_reads_an_indicator_the_control_draws_inside_or_around_it(tmp_path):
    """Refresh field run: a chart point showed its focus by revealing a marker inside it, with no outline of its own, and
    was read as having no indicator; a wrapper's :focus-within ring is drawn outside the control's own style too, and a
    chart's script marks the point it focuses with a class it keeps after blur. What focus changes on screen, in and
    around the control, against the page before the Tab, is the indicator; a control focus leaves unchanged has none."""
    entry = _write_html(
        tmp_path / "drawn-focus.html",
        """
<main>
  <h1>Chart</h1>
  <div style="height: 1200px">Intro</div>
  <svg width="340" height="80" role="img" aria-label="Chart">
    <g class="pt" tabindex="0" aria-label="May"><circle cx="30" cy="40" r="6"/><rect class="marker" x="20" y="10" width="20" height="60"/></g>
    <g class="pt bare" tabindex="0" aria-label="June"><circle cx="90" cy="40" r="6"/></g>
    <g class="pt js" tabindex="0" aria-label="July"><circle cx="150" cy="40" r="6"/><rect class="guide" x="149" y="0" width="2" height="80"/></g>
    <g class="pt seen" tabindex="0" aria-label="August"><circle cx="210" cy="40" r="6"/></g>
    <g class="pt js2" tabindex="0" aria-label="September"><circle cx="270" cy="40" r="6"/><rect class="guide" x="282" y="0" width="10" height="80"/></g>
    <g class="pt bare" tabindex="0" aria-label="October"><circle cx="300" cy="40" r="6"/></g>
  </svg>
  <span class="wrap"><button class="inner">Filter</button></span>
  <span class="wrap multi"><button class="inner">Day</button><button class="inner">Week</button><button class="inner">Month</button></span>
</main>
<script>
  document.querySelector('.js').addEventListener('focus', (e) => e.currentTarget.classList.add('on'));    // kept after blur
  document.querySelector('.seen').addEventListener('focus', (e) => e.currentTarget.setAttribute('data-seen', '1'));  // draws nothing
  // a guide shown while focused, drawn into the next point's box: put back, it would read as October's indicator
  const s = document.querySelector('.js2');
  s.addEventListener('focus', () => s.classList.add('on')); s.addEventListener('blur', () => s.classList.remove('on'));
</script>
""",
        """
<style>
  body { font-family: system-ui, sans-serif; color: #111; background: #fff; }
  html { scroll-behavior: smooth; }   /* the chart is below the fold: read after the scroll, not mid-way */
  .pt:focus { outline: none; } .marker { fill: #005fcc; opacity: 0; } .pt:focus-visible .marker { opacity: 1; }
  .guide { fill: #005fcc; opacity: 0; } .js.on .guide, .js2.on .guide { opacity: 1; }
  .wrap { display: inline-block; margin: 16px; border-radius: 6px; }
  .inner { min-width: 80px; min-height: 44px; border: 0; } .inner:focus { outline: none; }
  .wrap:focus-within { box-shadow: 0 0 0 3px #005fcc; }
</style>
""",
    )

    _, res = _run(entry, tmp_path / "out")

    dim = res.dimensions["A11Y-FOCUS"]
    assert [f["message"] for f in dim.findings] == ["no visible focus on g 'June'", "no visible focus on g 'August'",
                                                    "no visible focus on g 'October'",
                                                    "no visible focus on button 'Week'",
                                                    "no visible focus on button 'Month'"], dim.findings


def test_reduced_motion_sweeps_every_screen(tmp_path):
    entry = _write_html(
        tmp_path / "motion.html",
        """
<main>
  <h1>Reduced motion</h1>
  <div id="spinner" aria-label="Loading"></div>
</main>
""",
        """
<style>
  body { font-family: system-ui, sans-serif; color: #111; background: #fff; }
  #spinner { width: 48px; height: 48px; border: 6px solid #444; animation: spin 2s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
""",
    )
    screens = [
        {"id": "one", "route": "#one"},
        {"id": "two", "route": "#two"},
        {"id": "three", "route": "#three"},
        {"id": "four", "route": "#four"},
    ]

    rep, res = _run(entry, tmp_path / "out", screens=screens)

    assert any(hit["screen"] == "four" for hit in rep["reduced_motion"])
    assert not res.dimensions["A11Y-REDUCED-MOTION"].passed


def test_plan_schema_rejects_scenario_steps_with_multiple_actions():
    with pytest.raises(ValueError, match="exactly one"):
        PrototypePlan.model_validate(
            {
                "goals": ["Ship"],
                "fidelity": "high",
                "fidelity_rationale": "Real-browser audit fixture.",
                "riskiest_assumptions": [],
                "customer_alignment": {"status": "aligned", "with_whom": "Wei", "evidence_ids": []},
                "scenarios": [
                    {
                        "id": "S-01",
                        "flow_id": "F-01",
                        "name": "Bad multi-action step",
                        "steps": [{"click": "#release", "expect_visible": "#missing"}],
                        "success": "The release is visible.",
                    }
                ],
                "states": [],
                "viewports": [390, 1440],
                "content_needs": [],
                "test_criteria": [],
                "out_of_scope": ["No production integration."],
            }
        )


def test_browser_runner_fails_scenario_steps_with_multiple_actions(tmp_path):
    entry = _write_html(
        tmp_path / "scenario.html",
        """
<main>
  <h1>Scenario</h1>
  <button id="release">Release</button>
</main>
""",
        """
<style>
  body { font-family: system-ui, sans-serif; color: #111; background: #fff; }
  button { min-width: 80px; min-height: 44px; }
</style>
""",
    )
    scenarios = [
        {
            "id": "S-01",
            "steps": [{"click": "#release", "expect_visible": "#missing"}],
        }
    ]

    rep, res = _run(entry, tmp_path / "out", scenarios=scenarios)

    scenario = rep["scenarios"][0]
    assert not scenario["passed"]
    assert scenario["failed_step"] == 1
    assert "exactly one" in scenario["error"]
    assert not res.dimensions["FUNC-SCENARIOS"].passed


def test_a_screen_route_that_does_not_render_its_screen_fails_func_states(tmp_path):
    """Field run W6: a representative route that names a record only a scenario creates was swept as its not-found
    page, so every browser check on that screen silently measured the error state instead."""
    entry = _write_html(
        tmp_path / "router.html",
        """
<main id="app"></main>
<script>
  function render() {
    document.getElementById('app').innerHTML = location.hash === '#one'
      ? '<section data-screen="one"><h1>One</h1></section>'
      : '<section data-state="error"><h1>Record not found</h1></section>';
  }
  window.addEventListener('hashchange', render);
  render();
</script>
""",
        "<style> body { font-family: system-ui, sans-serif; color: #111; background: #fff; } </style>",
    )
    screens = [{"id": "one", "route": "#one"}, {"id": "two", "route": "#two"}]

    rep, res = _run(entry, tmp_path / "out", screens=screens)

    rows = {r["screen"]: r for r in rep["screens"]}
    assert rows["one"]["renders_screen"] and not rows["two"]["renders_screen"]
    dim = res.dimensions["FUNC-STATES"]
    assert not dim.passed
    hit = [f for f in dim.findings if f["location"] == "two"]
    assert hit and "#two" in hit[0]["message"] and hit[0]["traced_node"] == "n11_prototype_development"
    assert "0/0 planned states" in dim.evidence and "1/2 screen routes" in dim.evidence


def test_expect_no_text_fails_while_a_retired_record_still_renders(tmp_path):
    """Field run 2, R2-04: the step DSL could assert text present but not absent, so a P0 acceptance "every view shows 0
    retired records" could not be encoded, and a build still rendering 9 of them passed every scenario."""
    pytest.importorskip("playwright")
    entry = _write_html(tmp_path / "p.html", '<main data-screen="one"><ul id="list"><li>Lot 7</li><li>Old supplier (retired)</li></ul></main>')
    scenario = {"id": "S-01", "flow_id": "F-01", "steps": [{"expect_no_text": ["#list li", "(retired)"]}]}
    rep, _ = _run(entry, tmp_path / "a", scenarios=[scenario])
    assert not rep["scenarios"][0]["passed"] and "still shows '(retired)'" in rep["scenarios"][0]["error"]
    clean = _write_html(tmp_path / "q.html", '<main data-screen="one"><ul id="list"><li>Lot 7</li></ul></main>')
    rep, _ = _run(clean, tmp_path / "b", scenarios=[scenario])
    assert rep["scenarios"][0]["passed"], rep["scenarios"][0]["error"]


def test_the_suite_prints_a_heartbeat_line_per_scenario_and_sweep(tmp_path, capsys):
    """Field run 2, R2-05: a 12-screen, 4-viewport suite ran 4-5 minutes printing nothing, so a hang looked like work."""
    pytest.importorskip("playwright")
    entry = _write_html(tmp_path / "p.html", '<main data-screen="one"><p>Lot 7</p></main>')
    _run(entry, tmp_path / "a", scenarios=[{"id": "S-01", "flow_id": "F-01", "steps": [{"expect_visible": "main"}]}])
    err = capsys.readouterr().err
    assert "pdg browser: 390 px · scenario S-01" in err and "pdg browser: 390 px · sweep of 1 screens" in err


def test_expect_reachable_fails_for_a_control_more_than_a_screen_away(tmp_path):
    """Backlog N-18: the completing control must be within one screen of scrolling from where the user is."""
    pytest.importorskip("playwright")
    far = _write_html(tmp_path / "far.html", '<main data-screen="one"><button id="go" style="margin-top:3000px">Close case</button></main>')
    near = _write_html(tmp_path / "near.html", '<main data-screen="one"><button id="go" style="margin-top:1000px">Close case</button></main>')
    scenario = {"id": "S-01", "flow_id": "F-01", "steps": [{"expect_reachable": "#go"}]}
    rep, _ = _run(far, tmp_path / "a", scenarios=[scenario])
    assert not rep["scenarios"][0]["passed"] and "more than one screen away" in rep["scenarios"][0]["error"]
    rep, _ = _run(near, tmp_path / "b", scenarios=[scenario])
    assert rep["scenarios"][0]["passed"], rep["scenarios"][0]["error"]


def test_the_plans_forbidden_text_is_scanned_on_every_screen_and_fails_the_scenarios_dimension(tmp_path):
    """Field run 2, R2-04: a P0 acceptance said no view may show a retired record, and a passing build showed 9 of them.
    The plan lists such text in `forbidden_text`, and the suite reads each screen and state it opens."""
    pytest.importorskip("playwright")
    from pdg.context import CheckResult
    entry = _write_html(tmp_path / "p.html", '<main data-screen="one"><p>Acme Foods (retired)</p></main>')
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], [{"id": "one", "route": ""}], [390], t, tmp_path / "run", forbidden=["(retired)"])
    res = CheckResult()
    browser.findings_from(rep, t, res)
    dim = res.dimensions["FUNC-SCENARIOS"]
    assert not dim.passed and "forbidden text shown" in dim.evidence
    assert any("shows the forbidden text '(retired)'" in f["message"] for f in dim.findings)
    clean = _write_html(tmp_path / "q.html", '<main data-screen="one"><p>Acme Foods</p></main>')
    rep = browser.run_suite(clean, [], [], [{"id": "one", "route": ""}], [390], t, tmp_path / "run2", forbidden=["(retired)"])
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert res.dimensions["FUNC-SCENARIOS"].passed and "none of 1 shown" in res.dimensions["FUNC-SCENARIOS"].evidence


ROUTER = """<main id="app"></main><script>
function show() { const r = location.hash === "#/case" ? "case" : "home";
  document.getElementById("app").innerHTML = `<section data-screen="${r}"><h1>${r}</h1></section>`; }
window.addEventListener("hashchange", show); %s show();
</script>"""


def test_a_deep_link_that_only_works_after_a_hash_change_fails_its_route_check(tmp_path):
    """Field run 2, R2-06: the sweep and every scenario opened the entry first, so each route was a same-document hash
    change and a router that ignores the initial hash passed. A shared link opens the route cold; so does the suite now."""
    pytest.importorskip("playwright")
    broken = _write_html(tmp_path / "b.html", ROUTER % 'if (location.hash) { location.hash = ""; }')
    ok = _write_html(tmp_path / "o.html", ROUTER % "")
    screens = [{"id": "home", "route": ""}, {"id": "case", "route": "#/case"}]
    scenario = {"id": "S-01", "flow_id": "F-01", "steps": [{"goto": "#/case"}, {"expect_visible": '[data-screen="case"]'}]}
    rep, res = _run(broken, tmp_path / "a", scenarios=[scenario], screens=screens)
    assert not rep["scenarios"][0]["passed"]
    assert not next(r for r in rep["screens"] if r["screen"] == "case")["renders_screen"]
    rep, res = _run(ok, tmp_path / "b", scenarios=[scenario], screens=screens)
    assert rep["scenarios"][0]["passed"] and all(r["renders_screen"] for r in rep["screens"])


def test_expect_no_text_fails_when_its_selector_matches_nothing(tmp_path):
    """Field run 2, R2-07: a selector that matched nothing passed, so a screen that never rendered passed its "never
    shows X" check, the very failure R2-06 hid."""
    pytest.importorskip("playwright")
    entry = _write_html(tmp_path / "p.html", '<main data-screen="home"><p>Lot 7</p></main>')
    scenario = {"id": "S-01", "flow_id": "F-01", "steps": [{"expect_no_text": ['[data-screen="hub"]', "(retired)"]}]}
    t = _thresholds()
    t["step_timeout_ms"] = 800
    rep = browser.run_suite(entry, [scenario], [], [{"id": "home", "route": ""}], [390], t, tmp_path / "run")
    assert not rep["scenarios"][0]["passed"]



def test_expect_reachable_accepts_any_selector_a_click_accepts_and_no_text_says_nothing_matched(tmp_path):
    """Independent audit #9 and #10: `expect_reachable` used `document.querySelector`, so a Playwright selector such as
    `text=Close case` raised a SyntaxError blamed on the build; `expect_no_text` on a missing selector only timed out."""
    pytest.importorskip("playwright")
    entry = _write_html(tmp_path / "p.html", '<main data-screen="one"><button>Close case</button></main>')
    t = _thresholds()
    t["step_timeout_ms"] = 800
    ok = {"id": "S-01", "flow_id": "F-01", "steps": [{"expect_reachable": "text=Close case"}]}
    none = {"id": "S-02", "flow_id": "F-01", "steps": [{"expect_no_text": ["#missing", "retired"]}]}
    rep = browser.run_suite(entry, [ok, none], [], [{"id": "one", "route": ""}], [390], t, tmp_path / "run")
    by = {s["id"]: s for s in rep["scenarios"]}
    assert by["S-01"]["passed"], by["S-01"]["error"]
    assert not by["S-02"]["passed"] and "matched nothing" in by["S-02"]["error"]


def test_the_canonical_colour_is_the_colour_chromium_computes_for_every_spelling():
    """Batch 7 review I4: rounding half to even, a 3-decimal alpha and bare hsl numbers made `canonical_colour` differ
    from the browser (`hsl(210 40% 50%)` → #4D7FB2, Chromium #4D80B3), so BLD-TOKENS could fail a declared colour.
    Each spelling's canonical form must equal the canonical form of what Chromium computes for it."""
    import pytest
    from pdg.tools._common import canonical_colour
    spellings = ["hsl(210 40% 50%)", "rgb(10% 20% 30%)", "#00000080", "rgba(0,0,0,.5)", "hsl(120 50 50)",
                 "rgb(255 255 255 / 40%)", "rgba(255,255,255,.4)", "#FFFFFF66", "#abc", "#abcd", "hsl(0.5turn 100% 50%)",
                 "hsla(210, 40%, 50%, 0.333)", "rgba(12, 34, 56, 0.07)", "hsl(33deg 77% 41% / 12%)", "rgb(1 2 3 / 0.999)",
                 "hsl(300 20% 83%)", "rgb(127.5 0.5 254.5)", "hsl(1rad 60% 40%)", "#7f7f7f80", "rgba(255,0,0,0.25)"]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            computed = page.evaluate("""(vals) => vals.map(v => { const d = document.createElement('div');
                d.style.color = v; document.body.appendChild(d); const c = getComputedStyle(d).color; d.remove(); return c; })""",
                                     spellings)
            b.close()
    except Exception as exc:  # noqa: BLE001
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium is not installed (python -m playwright install chromium)")
        raise
    def chromium_form(c: str) -> str:   # Chromium's own text: rgb(r, g, b) → #RRGGBB; rgba keeps its alpha as written
        if c.startswith("rgba("):
            return c.replace(" ", "")
        r, g, b = (int(x) for x in c[4:-1].split(","))
        return f"#{r:02X}{g:02X}{b:02X}"
    wrong = [(v, canonical_colour(v), c) for v, c in zip(spellings, computed) if canonical_colour(v) != chromium_form(c)]
    assert not wrong, wrong


def test_a_goto_to_the_current_url_arrives_at_the_top_and_every_later_goto_keeps_the_app_state(tmp_path):
    """Field run 1, W50: a goto to the URL the page was already on did nothing (no load, no hashchange), so the next
    reachability check measured from far down the page. It now returns to the top of the window and of every scroller,
    with Tab starting over, and keeps the app's in-memory state as a goto to another route does (review I2), at once
    even on a page that scrolls smoothly (review I3). The entry sits under a path with a space, a plus and an accent,
    and the route has one too, as a real project's does."""
    pytest.importorskip("playwright")
    folder = tmp_path / "A + B é"
    folder.mkdir()
    entry = _write_html(folder / "p.html", head="<style>html, #pane { scroll-behavior: smooth; }</style>", body="""<a id="skip" href="#main">Skip</a><main data-screen="rec"><h1>Record</h1>
<button id="see">See Related</button><button id="add">Add</button><p id="n">0</p><a rel="next" href="#/next">Next</a>
<div id="pane" style="height:120px;overflow:auto"><div style="height:2000px"></div></div>
<div style="height:4000px"></div><h2 id="related" tabindex="-1">Related</h2><button id="after">After</button></main>
<script>let n = 0; document.getElementById('see').onclick = () => { document.getElementById('pane').scrollTop = 1500;
  document.getElementById('related').focus(); };
document.getElementById('add').onclick = () => { n += 1; document.getElementById('n').textContent = String(n); };</script>""")
    t = _thresholds()
    t["step_timeout_ms"] = 800
    here = "#/topic/café"
    same = {"id": "S-01", "flow_id": "F-01", "steps": [{"goto": here}, {"click": "#add"}, {"click": "#see"}, {"goto": here},
                                                        {"expect_reachable": 'a[rel="next"]'}, {"expect_text": ["#n", "1"]},
                                                        {"press": "Tab"}, {"expect_focus": "#skip"}]}
    pane = {"id": "S-03", "flow_id": "F-01", "steps": [{"goto": here}, {"click": "#see"}, {"goto": here},
                                                        {"expect_in_viewport": "#pane > div"}]}
    other = {"id": "S-02", "flow_id": "F-01", "steps": [{"goto": here}, {"click": "#add"}, {"goto": "#/other"},
                                                         {"expect_text": ["#n", "1"]}]}
    rep = browser.run_suite(entry, [same, other, pane], [], [{"id": "rec", "route": here}], [390], t, tmp_path / "run")
    by = {s["id"]: s for s in rep["scenarios"]}
    for sid in ("S-01", "S-02", "S-03"):
        assert by[sid]["passed"], (sid, by[sid]["error"])


def test_w52_a_screen_marked_from_data_is_found_by_rendering_its_route(tmp_path, monkeypatch):
    """Field run 1, W52: a registry drove the feeds, so app.js wrote `data-screen="feed-${id}"`; the text scan could not
    read the id and BLD-SCREENS failed 7/9 while the browser suite rendered 9/9. A screen the scan misses is looked for
    on its own route, loaded cold; a screen no route shows still fails, and the message names the accepted forms."""
    pytest.importorskip("playwright")
    import json as _json
    from pdg.models import ProjectState
    from pdg.tools import prototype
    from .conftest import FakeCtx
    (tmp_path / "index.html").write_text("""<!doctype html><html><head><meta charset="utf-8"><title>x</title></head>
<body><main id="app"><section data-screen="home"><h1>Home</h1></section></main><script>
const TYPES = [{id: 'regulatory', name: 'Regulatory'}, {id: 'scientific', name: 'Scientific'}];
function route() { const m = location.hash.match(/^#\\/feed\\/(\\w+)$/); const t = m && TYPES.find(x => x.id === m[1]);
  if (t) document.getElementById('app').innerHTML = `<section data-screen="feed-${t.id}"><h1>${t.name}</h1></section>`; }
route(); window.addEventListener('hashchange', route);
</script></body></html>""")
    (tmp_path / "build-manifest.json").write_text(_json.dumps({"entry": "index.html", "stack": ["html"], "files": {},
                                                               "screens": {}}))
    screens = [{"id": "home", "name": "Home", "purpose": "Start", "route": "#/"},
               {"id": "feed-regulatory", "name": "Regulatory", "purpose": "Feed", "route": "#/feed/regulatory"},
               {"id": "feed-scientific", "name": "Scientific", "purpose": "Feed", "route": "#/feed/scientific"}]

    def bld(extra=()):
        state = ProjectState.model_validate({"schema_version": "t", "project": {"id": "t", "name": "t", "created": "now",
                                             "workflow_id": "w", "workflow_version": "1"},
                                             "design": {"screens": screens + list(extra)}})
        ctx = FakeCtx({}, state=state, work=tmp_path)
        ctx.output = lambda key: tmp_path if key == "prototype_build" else None
        return prototype.check_static(ctx).dimensions["BLD-SCREENS"]
    ok = bld()
    assert ok.passed and "3/3 screens implemented; 2 found by rendering their routes" in ok.evidence, ok.evidence
    media = {"id": "feed-media", "name": "Media", "purpose": "Feed", "route": "#/feed/media"}
    bad = bld([media])
    assert not bad.passed and "missing ['feed-media']" in bad.evidence and "data-screen=\"<id>\"" in bad.evidence, bad.evidence
    import pdg.tools.browser as b
    monkeypatch.setattr(b, "rendered_screens", lambda entry, routes, timeout_ms=3000: None)
    blind = bld()
    assert not blind.passed and "no browser" in blind.evidence, blind.evidence



W52_SHELL = """<nav>{nav}</nav><main id="app">{main}</main><script>
function route() {{ {router} }}
route(); window.addEventListener('hashchange', route);
</script>"""
W52_SCREENS = [("home", "#/"), ("case", "#/case"), ("audit", "#/audit"), ("lot", "#/lot")]


def _w52_screens(path: Path, **parts) -> dict:
    """A build whose markers are all written from data, so only rendering can find them; `parts` fill W52_SHELL."""
    _write_html(path, W52_SHELL.format(**{"nav": "", "main": "", "router": "", **parts}))
    return {s: r for s, r in W52_SCREENS}


def test_w52_a_marker_on_a_link_on_a_hidden_page_or_on_every_route_is_not_a_rendered_screen(tmp_path):
    """W52 review I1: a nav link carrying data-screen for highlighting, or screens stacked at opacity 0, made every
    route "render" every screen, in the new BLD-SCREENS fallback and in the route sweep alike. A marker counts when a
    user sees it, it is no link or navigation entry, and not every other route shows it too."""
    ids = [s for s, _ in W52_SCREENS]
    js_ids = "[" + ",".join(repr(i) for i in ids) + "]"
    nav = _w52_screens(tmp_path / "nav.html",
                       router=f"document.querySelector('nav').innerHTML = {js_ids}.map(s => "
                              "`<a href=\"#/${s}\" data-screen=\"${s}\">${s}</a>`).join('');")
    got = browser.rendered_screens(tmp_path / "nav.html", nav, timeout_ms=400)
    assert got["shown"] == set() and got["hidden"] == set(), got
    _w52_screens(tmp_path / "stack.html",
                 router=f"document.getElementById('app').innerHTML = {js_ids}.map(s => "
                        "`<div style=\"opacity:0\"><section data-screen=\"${s}\"><h1>${s}</h1></section></div>`).join('');")
    got = browser.rendered_screens(tmp_path / "stack.html", nav, timeout_ms=400)
    assert got["shown"] == set() and got["hidden"] == set(ids), got
    _w52_screens(tmp_path / "all.html",
                 router=f"document.getElementById('app').innerHTML = {js_ids}.map(s => "
                        "`<section data-screen=\"${s}\"><h1>${s}</h1></section>`).join('');")
    got = browser.rendered_screens(tmp_path / "all.html", nav)
    assert got["shown"] == set() and got["everywhere"] == set(ids), got
    one = {"case": nav["case"]}                                        # one route: compared with another screen's
    assert browser.rendered_screens(tmp_path / "all.html", one, {k: v for k, v in nav.items() if k != "case"})["everywhere"] == {"case"}
    _w52_screens(tmp_path / "ok.html",
                 router="const id = (location.hash.slice(2) || 'home'); document.getElementById('app').innerHTML = "
                        "`<section data-screen=\"${id}\"><h1>${id}</h1></section>`;")
    assert browser.rendered_screens(tmp_path / "ok.html", nav)["shown"] == set(ids)
    assert browser.rendered_screens(tmp_path / "ok.html", one, {"home": "#/"})["shown"] == {"case"}
    # the route sweep (FUNC-STATES) holds a route to the same rule
    screens = [{"id": s, "route": r} for s, r in W52_SCREENS]
    t = _thresholds()
    t["step_timeout_ms"] = 400

    def sweep(name):
        rep = browser.run_suite(tmp_path / name, [], [], screens, [390], t, tmp_path / f"run-{name}")
        res = CheckResult()
        browser.findings_from(rep, t, res)
        return rep, res.dimensions["FUNC-STATES"]
    for name in ("nav.html", "all.html"):                      # the helper covers the stacked page
        rep, dim = sweep(name)
        assert not any(r["renders_screen"] for r in rep["screens"]) and not dim.passed, name
    assert "its marker shows on every route" in json.dumps(dim.findings), dim.evidence
    # a link naming the screen on its own route (a breadcrumb) is not the screen, while the other routes render theirs
    _w52_screens(tmp_path / "crumb.html",
                 router="const id = (location.hash.slice(2) || 'home'); document.getElementById('app').innerHTML = "
                        "id === 'case' ? '<a href=\"#/case\" data-screen=\"case\">Case</a>' "
                        ": `<section data-screen=\"${id}\"><h1>${id}</h1></section>`;")
    crumb = browser.rendered_screens(tmp_path / "crumb.html", one, {"home": "#/"}, timeout_ms=400)
    assert crumb["shown"] == set() and crumb["linked"] == {"case"}, crumb            # and it says why
    rep, dim = sweep("crumb.html")
    assert {r["screen"]: r["renders_screen"] for r in rep["screens"]} == {"home": True, "case": False, "audit": True, "lot": True}
    # one missing route is compared with a screen that is not nested in it: a list stays beside its record
    _write_html(tmp_path / "md.html", """<main id="app"></main><script>
function route() { const h = location.hash; document.getElementById('app').innerHTML = h.startsWith('#/case/')
  ? '<section data-screen="case"><h1>Cases</h1></section><section data-screen="detail"><h1>C-1</h1></section>'
  : h === '#/case' ? '<section data-screen="case"><h1>Cases</h1></section>' : '<section data-screen="home"><h1>Home</h1></section>'; }
route(); window.addEventListener('hashchange', route);</script>""")
    got = browser.rendered_screens(tmp_path / "md.html", {"case": "#/case"}, {"detail": "#/case/1", "home": "#/"})
    assert got["shown"] == {"case"}, got
    # two missing, a list and its record: the record's route shows both; a third route decides (review, second pass)
    got = browser.rendered_screens(tmp_path / "md.html", {"case": "#/case", "detail": "#/case/1"}, {"home": "#/"})
    assert got["shown"] == {"case", "detail"} and not got["everywhere"], got
    got = browser.rendered_screens(tmp_path / "md.html", {"case": "#/case", "detail": "#/case/1"})   # no third route
    assert got["shown"] == {"case", "detail"}, got
    got = browser.rendered_screens(tmp_path / "md.html", {"case": "#/case"}, {"d1": "#/case/1", "d2": "#/case/2"})
    assert got["shown"] == {"case"}, got                             # its own records are no comparison for a list
    # a display: contents wrapper has no box; what it holds is the screen
    _write_html(tmp_path / "contents.html", '<section data-screen="x" style="display:contents"><h1>X</h1></section>')
    assert browser.rendered_screens(tmp_path / "contents.html", {"x": "#/x"})["shown"] == {"x"}


def test_w52_the_every_route_rule_needs_three_routes():
    """With two routes, a list shown beside its record on the record's route is not a marker on every route."""
    rep = {"screens": [{"screen": "case", "route": "#/case", "viewport": 390, "renders_screen": True, "shows": ["case"]},
                       {"screen": "detail", "route": "#/case/1", "viewport": 390, "renders_screen": True,
                        "shows": ["case", "detail"]}]}
    browser._everywhere(rep, 390)
    assert all(r["renders_screen"] for r in rep["screens"])
    rep["screens"].append({"screen": "home", "route": "#/", "viewport": 390, "renders_screen": True, "shows": ["home", "case"]})
    browser._everywhere(rep, 390)
    assert [r["screen"] for r in rep["screens"] if not r["renders_screen"]] == ["case"]


def test_w52_a_route_that_never_loads_is_named_and_the_render_has_a_time_budget(tmp_path):
    """W52 review S1, S2: a route stuck loading made the whole fallback answer "no browser" after Playwright's 30 s, and
    every missing screen cost its own timeout with no overall limit."""
    routes = _w52_screens(tmp_path / "stuck.html",
                          router="if (location.hash === '#/lot') { const t = Date.now(); while (Date.now() - t < 6000) {} } "
                                 "const id = (location.hash.slice(2) || 'home'); document.getElementById('app').innerHTML = "
                                 "`<section data-screen=\"${id}\"><h1>${id}</h1></section>`;")
    got = browser.rendered_screens(tmp_path / "stuck.html", routes, timeout_ms=500)
    assert got["unloaded"] == {"lot"} and got["shown"] == {"home", "case", "audit"}, got
    assert browser.rendered_screens(tmp_path / "stuck.html", routes, budget_s=0)["unchecked"] == set(routes)


def test_w53_sample_routes_take_the_plans_worst_cases_first_then_linked_records_spread_evenly():
    screens = [{"id": "list", "route": "#/list", "kind": "list"},
               {"id": "rec", "route": "#/rec/R-1", "kind": "record", "samples": ["#/rec/R-9", "#/rec/R-9"]},
               {"id": "form", "route": "#/form", "kind": "form", "samples": ["#/form?long=1"]}]
    links = {f"#/rec/R-{i}" for i in range(1, 21)} | {"#/rec/R-3/notes", "#/list", "#/other/R-2", "#/rec/R-4?tab=x", "#/rec/new"}
    screens.append({"id": "new", "route": "#/rec/new", "kind": "form"})
    got = browser.sample_routes(screens, links, cap=8)
    assert got["form"] == ["#/form?long=1"]                             # a plan's sample for any kind of screen
    rec = got["rec"]
    assert rec[0] == "#/rec/R-9" and len(rec) == 4 and len(set(rec)) == 4, rec   # 8 shared by 2 screens: 4 each
    assert "#/rec/R-1" not in rec and "#/rec/R-3/notes" not in rec and "#/other/R-2" not in rec
    assert not any("?" in r or r == "#/rec/new" for r in rec), rec      # a found link with a query, another screen
    assert sum(len(v) for v in browser.sample_routes(screens, links, cap=3).values()) <= 3   # the cap is a total
    assert rec[-1] == "#/rec/R-8", rec                                   # spread to the last of them, not the first few
    assert browser.sample_routes([{"id": "rec", "route": "#/rec/R-1", "kind": "record"}],
                                 {"#/rec/R-2", "#/rec/R-2/notes"}) == {"rec": ["#/rec/R-2"]}   # one level below only
    assert browser.sample_routes([{"id": "home", "route": "#/", "kind": "dashboard"}], links) == {}
    cut: dict = {}
    many = [{"id": "rec", "route": "#/rec/R-1", "kind": "record", "samples": [f"#/rec/W-{i}" for i in range(5)]}]
    assert browser.sample_routes(many, set(), cap=2, cut=cut) == {"rec": ["#/rec/W-0", "#/rec/W-1"]}
    assert cut == {"rec": ["#/rec/W-2", "#/rec/W-3", "#/rec/W-4"]}              # named, never dropped silently
    widths = list(range(340, 390, 20)) + list(range(390, 1440, 20)) + [1440]
    thin = browser._thin(widths, [390, 768, 1280, 1440])
    assert {340, 360, 380, 390, 750, 1270, 1440} <= set(thin) and len(thin) <= 12, thin   # below, each planned, the widest


W53_RECORDS = """<main id="app"></main><script>
const recs = Array.from({length: 8}, (_, i) => ({id: 'R-' + (i + 1), wide: i % 3 === 1}));
function route() {
  const h = location.hash, app = document.getElementById('app');
  const r = recs.find((x) => '#/rec/' + x.id === h);
  const wide = '<div style="width:480px">wide</div>';
  app.innerHTML = r
    ? `<section data-screen="rec"><h1>${r.id}</h1><div style="display:flex">${r.wide
        ? '<button style="flex:none;width:420px">Previous · Next · Open the source</button>' : '<button>Next</button>'}</div></section>`
    : h === '#/rec/new' ? `<section data-screen="rec-new"><h1>New record</h1>${wide}</section>`
    : h === '#/rec/all' ? '<section data-screen="list"><h1>Records</h1></section><section data-screen="rec"><h1>R-1</h1>'
      + wide + '</section>'
    : h.startsWith('#/rec/') ? `<p>Record not found</p>${wide}`
    : '<section data-screen="list"><h1>Records</h1>' + recs.map((x) => `<a href="#/rec/${x.id}">${x.id}</a>`).join(' ')
      + ' <a href="#/rec/new">New</a> <a href="#/rec/R-99">R-99</a> <a href="#/rec/all">All</a></section>';
}
const later = () => setTimeout(route, 250);   // the app renders after load, as many do (past the 120 ms settle)
later(); window.addEventListener('hashchange', later);
</script>"""


def test_w53_the_width_checks_load_more_records_of_a_record_screen_and_start_at_the_reflow_width(tmp_path):
    """Field run 1, W53: the suite loaded each screen at the one route N07 named, so a third head action that
    overflowed 17 of 31 records at 320 px passed four rounds (the sampled record had only two). Records the app links to
    under the same route are loaded too; and the band starts at the reflow width, so 321–389 px are read."""
    entry = _write_html(tmp_path / "records.html", W53_RECORDS)
    screens = [{"id": "list", "route": "#/list", "kind": "list"}, {"id": "rec", "route": "#/rec/R-1", "kind": "record"},
               {"id": "rec-new", "route": "#/rec/new", "kind": "form"}]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 600], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert rep["samples"] == {"rec": [f"#/rec/R-{i}" for i in range(2, 9)]}, rep["samples"]   # not another screen
    assert rep["samples_dropped"] == {"rec": ["#/rec/R-99", "#/rec/all"]}   # a missing record; a list with a record pane
    reflow = res.dimensions["RESP-REFLOW-320"]
    assert not reflow.passed, reflow.evidence
    assert "on 3 of 8 routes loaded" in json.dumps(reflow.findings) and "#/rec/R-2" in json.dumps(reflow.findings), reflow.findings
    assert "samples dropped, they do not render their screen alone: rec #/rec/R-99, #/rec/all" in reflow.evidence, reflow.evidence
    assert "rec overflows by" in json.dumps(reflow.findings) and "rec-new overflows by" in json.dumps(reflow.findings)
    assert not any(x in json.dumps(reflow.findings) for x in ("R-99", "#/rec/new", "#/rec/all"))   # each its own
    band = res.dimensions["RESP-BAND"]
    assert not band.passed and "rec at 340–390 px (on sampled records #/rec/R-2, #/rec/R-5, #/rec/R-8)" in band.evidence, \
        band.evidence
    assert "screens swept at 340–600 px" in band.evidence, band.evidence    # 320 itself is the reflow pass's

    # a layout that breaks only between the reflow width and the narrowest planned width
    narrow = _write_html(tmp_path / "narrow.html", '<main data-screen="one"><div class="x">wide</div></main>',
                         head="<style>@media (min-width: 330px) and (max-width: 389px) { .x { width: 480px } }</style>")
    rep = browser.run_suite(narrow, [], [], [{"id": "one", "route": ""}], [390, 600], t, tmp_path / "run2")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert not res.dimensions["RESP-BAND"].passed and "340–380 px" in res.dimensions["RESP-BAND"].evidence, \
        res.dimensions["RESP-BAND"].evidence
    assert res.dimensions["RESP-REFLOW-320"].passed and res.dimensions["RESP-OVERFLOW"].passed



def test_w53_findings_name_sampled_records_count_each_width_once_and_never_pass_an_unread_design_route():
    """W53 review I3, I4, S6: every RESP-TEXT problem is a finding in a fixed order; a problem seen on the design route
    and a sample at one width is one width; a design route that would not load fails the reflow check, a sample that
    would not load is named."""
    rep = {"reference": None, "scenarios": [], "states": [], "screens": [], "axe": [], "reduced_motion": [], "console": [],
           "requests": [], "timing_ms": [], "forbidden_text": [], "tokens": [], "parity": [], "band_step": 20,
           "samples_cut": {"rec": ["#/rec/W-3"]},
           "reflow_320": [{"screen": "rec", "route": "#/rec/1", "sample": False, "overflow_px": 0},
                          {"screen": "rec", "route": "#/rec/2", "sample": True, "overflow_px": 0, "error": "Timeout 15000ms"}],
           "band": [{"screen": f"s{i:02}", "route": f"#/s{i:02}", "width": 340, "overflow": 0, "midword": [],
                     "spill": [{"el": "div.tile", "px": 4}]} for i in reversed(range(14))]      # seen out of order
           + [{"screen": "rec", "route": "#/rec/1", "width": 340, "overflow": 30, "midword": [], "spill": []},
              {"screen": "rec", "route": "#/rec/9", "sample": True, "width": 340, "overflow": 30, "midword": [],
               "spill": [{"el": "span.pill", "px": 6}]}]}
    t = _thresholds()
    res = CheckResult()
    browser.findings_from(rep, t, res)
    band, text, reflow = (res.dimensions[d] for d in ("RESP-BAND", "RESP-TEXT", "RESP-REFLOW-320"))
    assert "rec at 340 px (on sampled record #/rec/9)" in band.evidence and "340 px, 340 px" not in band.evidence, band.evidence
    assert len(text.findings) == 15 and "(on sampled record #/rec/9)" in json.dumps(text.findings), len(text.findings)
    assert [f["location"] for f in text.findings] == sorted(f["location"] for f in text.findings)
    assert reflow.passed and "not read: rec #/rec/2: Timeout" in reflow.evidence, reflow.evidence
    assert "plan samples not read, over their screen's share of the 24-route cap: rec #/rec/W-3" in reflow.evidence
    rep["reflow_320"][0].update(error="Timeout 15000ms")                  # the design route itself was not read
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert not res.dimensions["RESP-REFLOW-320"].passed



def test_w53_the_suite_screens_keep_each_screens_kind_so_records_are_found():
    """W53: the suite finds more records of a `record` screen from the app's links, by the screen's kind. The example
    plan now names its worst cases itself, so the end-to-end run no longer shows that the kind reaches the suite."""
    design = [{"id": "list", "route": "#/list", "kind": "list"}, {"id": "rec", "route": "#/rec/R-1", "kind": "record"}]
    screens = browser.suite_screens(design, {})
    assert [s["kind"] for s in screens] == ["list", "record"]
    assert browser.sample_routes(screens, {"#/rec/R-2", "#/rec/R-3", "#/list"}) == {"rec": ["#/rec/R-2", "#/rec/R-3"]}


def test_w53_the_sampled_records_have_a_time_budget(tmp_path):
    """W53 review I2: the samples are read within a time budget, and those left unread are counted, not dropped silently."""
    entry = _write_html(tmp_path / "records.html", W53_RECORDS)
    screens = [{"id": "list", "route": "#/list", "kind": "list"}, {"id": "rec", "route": "#/rec/R-1", "kind": "record"}]
    t = {**_thresholds(), "sample_budget_s": 0}
    rep = browser.run_suite(entry, [], [], screens, [390], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert "(7 not read: the samples' time budget ran out)" in res.dimensions["RESP-BAND"].evidence, res.dimensions["RESP-BAND"].evidence



def test_w53_a_record_that_renders_late_is_measured_rendered_at_every_width(tmp_path):
    """W53, the render waits: the band reads a record from its widest width down, and the DOM-quiet wait gives up
    before an app that renders 0.7 s after load has drawn anything, so the widest readings of a sampled record were of
    a blank page. The band waits for the record's screen first."""
    entry = _write_html(tmp_path / "late.html", """<main id="app"></main><script>
function route() { const app = document.getElementById('app'), h = location.hash;
  app.innerHTML = h === '#/rec/R-2' ? '<section data-screen="rec"><h1>R-2</h1><div style="width:900px">wide</div></section>'
    : h === '#/rec/R-1' ? '<section data-screen="rec"><h1>R-1</h1></section>'
    : '<section data-screen="list"><a href="#/rec/R-1">R-1</a> <a href="#/rec/R-2">R-2</a></section>'; }
const later = () => setTimeout(route, 700); later(); window.addEventListener('hashchange', later);
</script>""")
    screens = [{"id": "list", "route": "#/list", "kind": "list"}, {"id": "rec", "route": "#/rec/R-1", "kind": "record"}]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 600], t, tmp_path / "run")
    assert rep["samples"] == {"rec": ["#/rec/R-2"]}, rep
    res = CheckResult()
    browser.findings_from(rep, t, res)
    band = res.dimensions["RESP-BAND"].evidence
    assert "600 px (on sampled record #/rec/R-2)" in band, band            # its first, widest reading
    assert not res.dimensions["RESP-REFLOW-320"].passed                   # the reflow pass waits too


W55_PAGE = """<main data-screen="home"><h1>Signals</h1>
<select id="narrow" style="width:100px"><option>All regulatory types</option></select>
<select id="scope" style="width:110px"><option>Global</option><option>Latin America Operations Hub</option></select>
<select id="fit" style="field-sizing:content"><option>Global hub</option></select>
<select id="tight"><option>Watch list</option></select>
<span class="pill" id="pill" style="display:inline-block;background:#eee;white-space:nowrap"><span id="pt">Proposed</span></span>
<div id="w" style="overflow-wrap:anywhere">Contaminants</div>
<p><span id="line" style="white-space:nowrap">word</span></p></main>
<script>
// sized at load to fit exactly, so only the 1.4.12 spacing breaks them (W56)
const px = (e) => e.getBoundingClientRect().width;
const tight = document.getElementById('tight'), probe = tight.cloneNode(true);
probe.style.cssText = 'field-sizing:content;position:absolute;visibility:hidden'; tight.parentElement.appendChild(probe);
tight.style.width = (px(probe) + 2) + 'px'; probe.remove();
document.getElementById('pill').style.width = (px(document.getElementById('pt')) + 4) + 'px';
const w = document.getElementById('w'), m = document.createElement('span'); m.textContent = w.textContent;
document.body.appendChild(m); w.style.width = (px(m) + 2) + 'px'; m.remove();
const line = document.getElementById('line');
while (px(line) < window.innerWidth - 40) line.textContent += ' word';
</script>"""


def test_w55_w56_w57_a_cut_select_value_and_what_text_spacing_breaks_are_found(tmp_path):
    """Field run 1, W55: a select's value is not DOM text, so a topbar that cut "Global hub" to "Global …" passed every
    text check. W56: the 1.4.12 check read only clipping, at the widest width, so a pill's text past its edge and a word
    broken mid-word under spacing passed. W57: a select sized exactly to its text is not cut (measured on its box, not
    the rounded clientWidth)."""
    entry = _write_html(tmp_path / "p.html", W55_PAGE, head="<style>body { font: 14px Arial, sans-serif; }</style>")
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], [{"id": "home", "route": ""}], [390, 600], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    text = res.dimensions["RESP-TEXT"].evidence
    assert "home: select#narrow shows 'All regulatory types' cut at 340–600 px" in text, text
    assert text.split("; ")[1].startswith(f"{len(res.dimensions['RESP-TEXT'].findings)} findings by screen: home "), text
    assert "home: select#scope its option 'Latin America Operations Hub' would be cut at" in text, text   # not shown
    assert "select#fit" not in text.split("under 1.4.12")[0] and "select#tight shows" not in text, text   # exact fits
    for what in ("home: span#pill.pill runs past its box under 1.4.12 text spacing at 390, 600 px",
                 "home: select#tight cuts its value 'Watch list' under 1.4.12 text spacing at 390, 600 px",
                 "home: overflows the page under 1.4.12 text spacing at 390, 600 px",
                 "home: div#w breaks a word mid-word 'Contaminants' under 1.4.12 text spacing at 390, 600 px"):
        assert what in text, (what, text)
    assert res.dimensions["A11Y-TEXT-SPACING-1412"].passed               # the adopted rule reads clipping; no clipping here
    elements = {f["element"] for f in res.dimensions["RESP-TEXT"].findings}
    assert {"select#narrow", "select#scope", "span#pill.pill (runs past its box under 1.4.12 spacing)"} <= elements, elements


W63_SIZED = """<main data-screen="home"><div style="width:360px">
<select id="grows" style="field-sizing:content;max-width:100%"><option>Global</option><option>Latin America Operations Hub</option></select>
</div><div style="width:120px">
<select id="capped" style="field-sizing:content;max-width:100%"><option>Global</option><option>Latin America Operations Hub</option></select>
</div><select id="fixed" style="width:110px"><option>Global</option><option>Latin America Operations Hub</option></select>
<div style="width:360px"><select id="grouped" style="field-sizing:content;max-width:100%"><optgroup label="A"><option>x</option>
<option>Global</option></optgroup><optgroup label="B"><option selected>Mid</option><option>Latin America Operations Hub</option>
</optgroup></select></div>
<div style="width:360px"><select id="empty" style="field-sizing:content;max-width:100%"><option>Global</option>
<option>Latin America Operations Hub</option></select></div>
<select id="off" style="width:60px"><option>A</option><optgroup label="Closed" disabled><option>A very long option no one can pick</option></optgroup></select></main>
<script>document.getElementById('empty').selectedIndex = -1;
window.__seen = []; for (const e of ['change', 'input'])
  document.addEventListener(e, (ev) => window.__seen.push(ev.type + ':' + ev.target.id), true);</script>"""


def test_w63_a_select_sized_to_its_value_is_read_with_the_option_chosen(tmp_path):
    """Field run W63: a `field-sizing: content` select is as wide as its current value, so the projection said every
    longer option "would be cut", though choosing it widens the select: 36 false clauses on a released build, as tool
    findings no build could answer. Such a select is now read with the option chosen, up to its max-width, and its value
    put back with no event fired. A fixed-width select keeps the projection, which found the real defect."""
    from playwright.sync_api import sync_playwright
    entry = _write_html(tmp_path / "p.html", W63_SIZED, head="<style>body { font: 14px Arial, sans-serif; }</style>")
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 600, "height": 700})
        page.goto(entry.as_uri())
        cut = {x["el"]: x for x in page.evaluate(browser.JS_BAND)["cut"]}
        assert set(cut) == {"select#capped", "select#fixed"}, cut   # grows fits once chosen; capped cannot; a disabled
        # group's option is no choice (review S10)
        assert not cut["select#capped"]["shown"] and cut["select#capped"]["text"] == "Latin America Operations Hub"
        assert page.evaluate("() => [window.__seen, ...['grows', 'capped', 'fixed'].map((i) => "
                             "document.getElementById(i).value)]") == [[], "Global", "Global", "Global"]
        assert page.evaluate("() => ['grouped', 'empty'].map((i) => document.getElementById(i).selectedIndex)") \
            == [2, -1]                                                      # put back as found (review S5)
        b.close()


W55_PROBE = """<main data-screen="home"><div class="bar"><select id="first"><option>Global hub</option></select>
<select id="later"><option>Global hub</option></select></div>
<div class="narrow"><select id="clamped"><option>Latin America Operations Hub</option></select></div>
<select id="placeholder" style="field-sizing:content"><option hidden disabled>Choose an operating unit…</option>
<option selected>Europe</option></select>
<select id="held" style="width:90px"><option hidden disabled>Choose an operating unit…</option><option selected>Europe</option></select>
<select id="forced" style="width:40px !important"><option>Latin America Operations Hub</option></select>
<div style="zoom:.8"><select id="zoomed" style="field-sizing:content"><option>Global hub</option></select></div>
<div style="transform:scale(.9)"><select id="scaled" style="field-sizing:content"><option>Global hub</option></select></div>
<select id="none" style="width:60px"><option>North America OU hub</option></select>
<div><select id="a"><option>North America OU hub</option></select></div>
<div><select id="b"><option>North America OU hub</option></select></div></main>
<script>
document.getElementById('none').selectedIndex = -1;   // it shows nothing: only its option can be cut
// a and b are 0.3 and 0.6 px narrower than their value needs: only b is cut (W57)
for (const [id, short] of [['a', 0.3], ['b', 0.6]]) {
  const s = document.getElementById(id), p = s.cloneNode(true);
  p.style.cssText = 'field-sizing:content;position:absolute;visibility:hidden'; s.parentElement.appendChild(p);
  s.style.width = (p.getBoundingClientRect().width - short) + 'px'; p.remove(); }
</script>"""


def test_w55_the_select_probe_ignores_page_rules_and_hidden_options_and_keeps_half_a_pixel(tmp_path):
    """Batch 13 review I1, I6: a probe appended to the select's parent took `select:first-child` padding it should not,
    lost to an !important width, and counted a hidden placeholder; and nothing tested the 0.5 px tolerance."""
    entry = _write_html(tmp_path / "p.html", W55_PROBE, head="""<style>body { font: 14px Arial, sans-serif; }
.bar select { field-sizing: content; padding-right: 40px; } .bar select:first-child { padding-right: 4px; }
.narrow select { max-width: 90px; }</style>""")
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], [{"id": "home", "route": ""}], [600], t, tmp_path / "run")
    cut = {x["el"] for r in rep["band"] if r.get("width") for x in r.get("cut", [])}
    assert cut == {"select#forced", "select#b", "select#clamped", "select#none"}, cut
    assert not any(x["shown"] for r in rep["band"] if r.get("width") for x in r.get("cut", []) if x["el"] == "select#none")
    # not #zoomed or #scaled: an ancestor's zoom or scale changes neither width compared (review IA)
    assert {"select#first", "select#forced"} <= set(next(r for r in rep["band"] if r.get("width"))["selects"])   # where they exist
    # not #first (a sibling rule), #placeholder (a hidden option) or #a (0.3 px short); #clamped only if the page's
    # max-width does not reach the probe


W55_BUDGET = """<main id="app"></main><script>
function route() {
  const app = document.getElementById('app');
  if (location.hash === '#/b') {   // sized once at load: wider than the window only while it is resized (W47 I1)
    app.innerHTML = '<section data-screen="b"><h1>Chart</h1><div id="chart" style="height:10px;background:#ccc"></div></section>';
    document.getElementById('chart').style.width = (window.innerWidth - 20) + 'px';
  } else {
    app.innerHTML = '<section data-screen="a"><h1>Filters</h1><select style="width:60px"><option>North America OU hub</option></select></section>';
  }
}
route(); window.addEventListener('hashchange', route);
</script>"""


def test_w55_a_cut_select_does_not_use_up_the_confirmations_another_screen_needs(tmp_path):
    """Batch 13 review C1: a select cut at every width filled the 60 fresh-load confirmations, so a chart sized once at
    load (wider than the window only while it is resized) failed RESP-BAND again. What a resize can fake is confirmed
    first."""
    entry = _write_html(tmp_path / "p.html", W55_BUDGET)
    screens = [{"id": "a", "route": "#/a"}, {"id": "b", "route": "#/b"}]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 1440], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert res.dimensions["RESP-BAND"].passed, res.dimensions["RESP-BAND"].evidence
    assert "a: select shows 'North America OU hub' cut" in res.dimensions["RESP-TEXT"].evidence


def test_w56_only_what_the_spacing_breaks_counts():
    """A page that already overflows, a box already spilled, a select already cut: none is a 1.4.12 failure, since the
    spacing did not cause it (the audit #3 rule, kept for the new readings)."""
    plain = {"overflow": 30, "spill": [{"el": "span.a", "px": 3, "text": "Proposed regulation"}],
             "cut": [{"el": "select#s", "px": 5, "text": "North America OU hub"}],
             "midword": [{"word": "Contaminants", "el": "div#w"}]}
    spaced = {"overflow": 60, "spill": [{"el": "span.a", "px": 9, "text": "Proposed regulation"},
                                        {"el": "span.b", "px": 4, "text": "Watch"},
                                        {"el": "span.a", "px": 17, "text": "Watch"}],   # another pill with the same label
              "cut": [{"el": "select#s", "px": 9, "text": "North America OU hub"}, {"el": "select#t", "px": 2, "text": "Europe"},
                      {"el": "select#s", "px": 3, "text": "Global hub"}],
              "midword": [{"word": "Contaminants", "el": "div#w"}, {"word": "Regulatory", "el": "h2"}]}
    got = browser._spacing_breaks(plain, spaced)
    assert got["text_spacing_overflow"] == 0
    assert [(x["el"], x["text"]) for x in got["text_spacing_spill"]] == [("span.b", "Watch"), ("span.a", "Watch")]
    assert [(x["el"], x["text"]) for x in got["text_spacing_cut"]] == [("select#t", "Europe"), ("select#s", "Global hub")]
    assert [x["word"] for x in got["text_spacing_midword"]] == ["Regulatory"]
    assert browser._spacing_breaks({**plain, "overflow": 0}, spaced)["text_spacing_overflow"] == 60



def test_w55_a_shell_select_is_one_finding_and_unread_clipping_fails_1412():
    """Batch 13 review I4, S3: a topbar select cut on every screen made one advisory defect per screen; and a spacing
    pass that failed at the widest width must not pass the adopted clipping check unmeasured."""
    cut = {"el": "select#ou", "px": 9, "text": "Global hub", "shown": True}
    rep = {"reference": None, "scenarios": [], "states": [], "axe": [], "reduced_motion": [], "console": [], "requests": [],
           "timing_ms": [], "forbidden_text": [], "tokens": [], "parity": [], "band_step": 20, "reflow_320": [],
           "screens": [{"screen": "home", "route": "#/", "viewport": 1440, "overflow_px": 0, "renders_screen": True,
                        "shows": ["home"], "small_targets": [], "small_targets_44": [], "small_text": [],
                        "focus_missing": [], "focus_obscured": [], "text_spacing_clipped": [],
                        "text_spacing_error": "Execution context was destroyed", "text_spacing_widest": True}],
           "band": [{"screen": scr, "route": f"#/{scr}", "width": 900, "overflow": 0, "midword": [], "spill": [], "cut": [cut],
                     "selects": ["select#ou"]} for scr in ("home", "cases", "feed")]}
    t = _thresholds()
    res = CheckResult()
    browser.findings_from(rep, t, res)
    text = res.dimensions["RESP-TEXT"]
    assert [f["location"] for f in text.findings] == ["shell"], text.findings
    assert "shell: select#ou shows 'Global hub' cut at 900 px (cut on 3 of 3 screens: cases, feed, home)" in text.evidence, text.evidence
    spacing = res.dimensions["A11Y-TEXT-SPACING-1412"]
    assert not spacing.passed and "not measured: home@1440" in spacing.evidence, spacing.evidence
    # a later build fixes two screens first: still one finding, at `shell`, so the defect keeps its identity (review IB)
    for r in rep["band"]:
        if r["screen"] != "home":
            r["cut"] = []
    res = CheckResult()
    browser.findings_from(rep, t, res)
    text = res.dimensions["RESP-TEXT"]
    assert [f["location"] for f in text.findings] == ["shell"], text.findings
    assert "(cut on 1 of 3 screens: home)" in text.evidence, text.evidence
    # two different selects without an id are never merged across screens
    other = {"el": "select.form-select", "px": 4, "text": "Owner", "shown": True}
    rep["band"] = [{"screen": scr, "route": f"#/{scr}", "width": w, "overflow": 0, "midword": [], "spill": [], "cut": [other],
                    "selects": []} for scr, w in (("cases", 600), ("signal", 900))]
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert sorted(f["location"] for f in res.dimensions["RESP-TEXT"].findings) == ["cases", "signal"]
    # one id with a class per screen is still one select; two words one element breaks are one finding; a reading that
    # only ever had a cut is no resize-only reading (review round 3)
    rep["band"] = [{"screen": scr, "route": f"#/{scr}", "width": 900, "overflow": 0, "midword": [], "spill": [],
                    "cut": [dict(cut, el=f"select#ou.{cls}")], "selects": ["select#ou"],
                    "resize_only": {"overflow": 0, "midword": [], "spill": [], "cut": [cut]}, "confirmed": True}
                   for scr, cls in (("home", "a"), ("cases", "b"))]
    rep["screens"][0].update(text_spacing_error=None, text_spacing_widest=None,
                             text_spacing_midword=[{"word": "Contaminants", "el": "h2"}, {"word": "Regulatory", "el": "h2"}])
    res = CheckResult()
    browser.findings_from(rep, t, res)
    text = res.dimensions["RESP-TEXT"]
    assert [f["location"] for f in text.findings if f["element"].startswith("select")] == ["shell"], text.findings
    assert len([f for f in text.findings if f["element"].startswith("h2")]) == 1, text.findings
    assert "'Contaminants', 'Regulatory'" in text.evidence and "clear on a fresh load" not in text.evidence, text.evidence


W58_FILTERS = """<main id="app"></main><script>
function route() {
  document.getElementById('app').innerHTML = '<section data-screen="list"><h1>Signals</h1>'
    + '<div style="display:flex;gap:8px;align-items:center"><select id="study"><option>All study types</option>'
    + '<option>Authority evaluation (document)</option></select><span id="chip" style="white-space:nowrap"></span></div></section>';
  const s = document.getElementById('study'), chip = document.getElementById('chip');
  s.style.width = '140px';
  s.addEventListener('change', () => { chip.textContent = 'Showing ' + s.value; });   // a chosen value widens the row
}
route(); window.addEventListener('hashchange', route);
</script>"""


def test_w58_a_layout_a_long_chosen_value_breaks_is_found_at_phone_widths(tmp_path):
    """Field run 1, W58 (D-214): every sweep loaded each screen with its filters at their defaults, the shortest
    values, so a Filters row that a long chosen study type widened past a 320 px phone passed every check until a
    reviewer chose it. Each select's longest option is now chosen as a user would and the phone widths read again."""
    entry = _write_html(tmp_path / "p.html", W58_FILTERS, head="<style>body { font: 14px Arial, sans-serif; margin: 8px; }</style>")
    screens = [{"id": "list", "route": "#/list", "kind": "list"}]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 800], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    band = res.dimensions["RESP-BAND"]
    assert not band.passed, band.evidence
    assert "list at 320–390 px once select#study shows 'Authority evaluation (document)'" in band.evidence, band.evidence
    assert [f["element"] for f in band.findings] == ["select#study = 'Authority evaluation (document)'"], band.findings
    assert "1 select value(s) chosen and read at 320–390 px" in band.evidence
    assert all(r.get("confirmed") for r in rep["chosen"] if r.get("width") and not r.get("spacing") and r["overflow"] > 1)
    rep = browser.run_suite(entry, [], [], screens, [390, 800], {**t, "chosen_budget_s": 0}, tmp_path / "run2")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    assert res.dimensions["RESP-BAND"].passed and "(1 screen(s) not read: the time budget ran out)" in res.dimensions["RESP-BAND"].evidence
    assert not [r for r in rep["chosen"] if r.get("width")]                # a spent budget reads no baseline either


R2_27_SHELL = """<header style="height:48px;background:#eee">Hub</header>
<main id="main" style="position:fixed;top:48px;bottom:0;left:0;right:0;overflow:auto"></main><script>
const HUB = '<section data-screen="hub"><h1>Materials</h1><select id="mat"><option>All</option><option>Polyethylene terephthalate</option></select>'
  + '<div class="card" style="background:#f4f4f4;padding:8px">'
  + '<div class="legend" style="display:flex;gap:8px"><span style="flex:none;width:220px">Polyethylene terephthalate</span>'
  + '<span style="flex:none;width:220px">High-density polyethylene</span><span style="flex:none;width:220px">Aluminium</span>'
  + '</div></div></section>';
// a wide tracker row inside a region the design scrolls sideways (a wide table's wrapper) is reachable there
const CASES = '<section data-screen="cases"><h1>Cases</h1><div class="tscroll" style="overflow-x:auto">'
  + '<div class="row" style="background:#fafafa;width:200px"><span style="display:inline-block;white-space:nowrap;width:1000px">'
  + 'Wide tracker row</span></div></div></section>';
function route() { document.getElementById('main').innerHTML = location.hash === '#/cases' ? CASES : HUB; }
route(); window.addEventListener('hashchange', route);
</script>"""


def test_r2_27_a_main_region_that_scrolls_sideways_is_page_overflow(tmp_path):
    """Field run 2, R2-27: at 390 px a legend ran 490 px past its card, but the document stayed as wide as the window
    because the app's `#main` (overflow auto) scrolled sideways instead. RESP-OVERFLOW and RESP-BAND read only the
    document, and RESP-TEXT counted what `#main` scrolls as reachable, so all three passed. The region around the view is
    now the page's; a region inside the view that scrolls sideways (a wide table's wrapper) is still reachable."""
    entry = _write_html(tmp_path / "p.html", R2_27_SHELL, head="<style>body { font: 14px Arial, sans-serif; margin: 0; }</style>")
    screens = [{"id": "hub", "route": "#/hub"}, {"id": "cases", "route": "#/cases"}]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 800], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    inside = "(inside main#main, which scrolls sideways around the screen)"
    over = res.dimensions["RESP-OVERFLOW"]
    assert [f["location"] for f in over.findings] == ["hub:390"], over.findings
    assert inside in over.findings[0]["message"], over.findings
    band = res.dimensions["RESP-BAND"]
    assert [f["location"] for f in band.findings] == ["hub"] and inside in band.findings[0]["message"], band.findings
    reflow = res.dimensions["RESP-REFLOW-320"]
    assert [f["location"] for f in reflow.findings] == ["hub:320"] and inside in reflow.findings[0]["message"], reflow.findings
    text = res.dimensions["RESP-TEXT"]
    assert "hub: div.card at" in text.evidence and "cases:" not in text.evidence, text.evidence
    assert "1 select value(s) chosen" in band.evidence and "with a value chosen" not in band.evidence   # adds nothing


W58_DISCLOSURE = """<main id="app"></main><script>
function route() {
  document.getElementById('app').innerHTML = '<section data-screen="feed"><h1>Studies</h1>'
    + '<button id="menu" aria-expanded="false" aria-controls="nav">Menu</button>'
    + '<nav id="nav" hidden><span style="display:inline-block;width:900px">Signals</span></nav>'
    + '<button id="more" aria-expanded="false" aria-controls="extra">Filters</button>'
    + '<div id="extra" hidden><div style="display:flex;gap:8px;align-items:center"><select id="study" style="width:140px">'
    + '<option>All study types</option><option>Authority evaluation (document)</option></select>'
    + '<span id="chip" style="white-space:nowrap"></span></div>'
    + '<span class="tag" style="display:inline-block;width:40px;white-space:nowrap;background:#eee">Regulatory evaluation</span> '
    + '<span class="pill" style="display:inline-block;white-space:nowrap;background:#eee"><span id="pt">Proposed</span></span></div>'
    + '<details><summary>More</summary><select id="year"><option>2024</option><option>Any publication year</option></select></details>'
    + '<div hidden><select id="never"><option>a</option><option>a longer one</option></select></div></section>';
  for (const [id, region] of [['menu', 'nav'], ['more', 'extra']]) {
    const b = document.getElementById(id), x = document.getElementById(region);
    b.addEventListener('click', () => { const open = b.getAttribute('aria-expanded') === 'true';
      b.setAttribute('aria-expanded', String(!open)); x.hidden = open;
      // sized to fit its text once shown, so only 1.4.12 spacing pushes it past its box
      if (!open && region === 'extra') x.querySelector('.pill').style.width =
        (document.getElementById('pt').getBoundingClientRect().width + 4) + 'px'; });
  }
  const s = document.getElementById('study'), chip = document.getElementById('chip');
  s.addEventListener('change', () => { chip.textContent = 'Showing ' + s.value; });
}
route(); window.addEventListener('hashchange', route);
</script>"""


def test_w58_a_select_behind_a_disclosure_is_chosen_with_the_disclosure_open(tmp_path):
    """Field run 1, W58 replayed on the real build: D-214's study type sat in a phone "Filters" panel that a button with
    aria-expanded and aria-controls opens, so the chosen-values pass, which read only visible selects, never chose it.
    The pass now opens such a disclosure (or a closed <details>) as a user would, compares the choice with the opened
    screen, and names the selects that stayed hidden."""
    entry = _write_html(tmp_path / "p.html", W58_DISCLOSURE, head="<style>body { font: 14px Arial, sans-serif; margin: 8px; }</style>")
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], [{"id": "feed", "route": "#/feed"}], [390, 800], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    band = res.dimensions["RESP-BAND"]
    assert [f["element"] for f in band.findings] == ["select#study = 'Authority evaluation (document)'"], band.findings
    assert "once select#study shows 'Authority evaluation (document)' (with button#more 'Filters' and summary 'More' open)" in band.findings[0]["message"]
    assert "2 select value(s) chosen and read at 320–390 px, with button#more 'Filters', summary 'More' opened" in band.evidence
    assert "selects hidden at 390 px were not chosen (1 on feed)" in band.evidence, band.evidence
    # the opened panel's own problems are its own (a Menu with no select in it stays closed), never a choice's
    both = "button#more 'Filters' and summary 'More' open"
    assert {f["element"] for f in res.dimensions["RESP-TEXT"].findings} == {
        f"span.tag (runs past its box with {both})", f"span.pill (runs past its box under 1.4.12 spacing with {both})",
        f"select#study (would cut its option with {both})"}, res.dimensions["RESP-TEXT"].findings
    assert "span.tag runs past its box at 320–390 px once button#more 'Filters' and summary 'More' are open" in \
        res.dimensions["RESP-TEXT"].evidence
    assert "Menu" not in json.dumps(rep["chosen_toggles"]), rep["chosen_toggles"]   # a disclosure with no select is never pressed
    for state in ("default", "opened"):                                   # each state is read at every phone width
        rows = [r for r in rep["chosen"] if r.get("width") and r["state"] == state and not r.get("spacing")]
        assert {r["width"] for r in rows} == set(rep["chosen_widths"]) and all(r["overflow"] <= 1 for r in rows), state


W58_REVIEW = """<main id="app"></main><script>
const long = '<option>All</option><option>Authority evaluation (document) and more</option>';
const S = {
  // I1: a "Filters" link that routes home, and a "Go to" select that routes home: home is not this screen
  nav: '<a id="f" href="#/home" aria-expanded="false" aria-controls="p">Filters</a><div id="p" hidden><select id="year">' + long
    + '</select></div><select id="go"><option>Here</option><option>Home and overview of everything</option></select>',
  // I2: the app keeps x in storage; y changes nothing
  saved: '<div style="display:flex;gap:8px"><select id="x" style="width:90px">' + long + '</select><span id="cx" style="white-space:nowrap"></span></div>'
    + '<select id="y"><option>Any</option><option>Some year</option></select>',
  // I3: an overlay covers the Sort toggle; z is visible and its long value widens the row
  stuck: '<button id="sort" aria-expanded="false" aria-controls="sp">Sort</button><div id="sp" hidden><select id="order">' + long
    + '</select></div><div style="position:fixed;inset:0;z-index:9"></div><div style="display:flex;gap:8px"><select id="z" style="width:90px">'
    + long + '</select><span id="cz" style="white-space:nowrap"></span></div>',
  // S-a, S-b: two numbered disclosures (one with a live count), and one whose click reveals nothing
  groups: '<button class="acc" aria-expanded="false" aria-controls="g1">Group 1</button><div id="g1" hidden><select id="g1s">' + long
    + '</select></div><button class="acc" aria-expanded="false" aria-controls="g2">Group 2 (3)</button><div id="g2" hidden>'
    + '<select id="g2s">' + long + '</select></div><button id="dud" aria-expanded="false" aria-controls="dx">More</button>'
    + '<div id="dx" hidden><select id="dxs">' + long + '</select></div>',
  // review S1: an accordion that keeps one group open; group 1's panel is wider than a phone
  accordion: [1, 2, 3, 4, 5].map((n) => '<button class="grp" aria-expanded="false" aria-controls="a' + n + '">Group ' + n
    + '</button><div id="a' + n + '" hidden>' + (n === 1 ? '<div style="width:420px;height:10px;background:#eee"></div>' : '')
    + '<select id="a' + n + 's">' + long + '</select></div>').join('') + '<select id="v"><option>Any</option><option>Some</option></select>',
  // S2: a chip sized at load to the window: a resize fakes an overflow a fresh load does not have
  late: '<select id="lt">' + long + '</select><div id="chip" style="background:#eee;height:10px"></div>',
};
function route() {
  const id = location.hash.slice(2) || 'home';
  if (id === 'home') { document.getElementById('app').innerHTML = '<section data-screen="home"><div style="width:900px">Home</div></section>'; return; }
  document.getElementById('app').innerHTML = '<section data-screen="' + id + '"><h1>' + id + '</h1>' + S[id] + '</section>';
  const on = (sel, fn) => { const e = document.querySelector(sel); if (e) e.addEventListener('change', fn); };
  on('#go', (e) => { if (e.target.selectedIndex) location.hash = '#/home'; });
  on('#x', (e) => { localStorage.setItem('x', e.target.selectedIndex); document.getElementById('cx').textContent = 'Showing ' + e.target.value; });
  const x = document.getElementById('x');
  if (x && localStorage.getItem('x')) { x.selectedIndex = +localStorage.getItem('x'); document.getElementById('cx').textContent = 'Showing ' + x.value; }
  on('#z', (e) => { document.getElementById('cz').textContent = 'Showing ' + e.target.value; });
  for (const b of document.querySelectorAll('.acc')) b.addEventListener('click', () => {
    b.setAttribute('aria-expanded', 'true'); document.getElementById(b.getAttribute('aria-controls')).hidden = false; });
  for (const b of document.querySelectorAll('.grp')) b.addEventListener('click', () => {
    for (const o of document.querySelectorAll('.grp')) { o.setAttribute('aria-expanded', 'false');
      document.getElementById(o.getAttribute('aria-controls')).hidden = true; }
    b.setAttribute('aria-expanded', 'true'); document.getElementById(b.getAttribute('aria-controls')).hidden = false; });
  const w = innerWidth;
  on('#lt', () => { document.getElementById('chip').style.width = (w - 30) + 'px'; });
}
route(); window.addEventListener('hashchange', route);
</script>"""


def test_w58_review_navigation_saved_values_stuck_toggles_and_resize_readings(tmp_path):
    """Batch 14 review: the chosen-values pass must not read another screen as this one (a disclosure link or a select
    that navigates, I1), must start each load with empty storage (a saved filter made an unrelated select look guilty,
    I2), must read the rest of a screen when one disclosure cannot be clicked (I3), and counts an overflow only when a
    fresh load confirms it against a fresh baseline (S1, S2)."""
    entry = _write_html(tmp_path / "p.html", W58_REVIEW, head="<style>body { font: 14px Arial, sans-serif; margin: 8px; }</style>")
    screens = [{"id": s, "route": f"#/{s}"} for s in ("nav", "saved", "stuck", "late", "groups", "accordion")]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 800], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    band = res.dimensions["RESP-BAND"]
    assert sorted(f["element"] for f in band.findings) == [
        "button.grp 'Group 1' open", "select#x = 'Authority evaluation (document) and more'",
        "select#z = 'Authority evaluation (document) and more'"], band.findings            # review S1: the accordion's panel
    assert "nav: a#f 'Filters' (leaves the screen)" in band.evidence and "stuck: button#sort 'Sort' (could not be clicked)" in band.evidence
    assert "nav select#go: choosing it leaves the screen" in band.evidence, band.evidence
    assert "with button.acc 'Group 1', button.acc 'Group 2', button.grp 'Group 1' opened to reach them" in band.evidence, band.evidence
    assert rep["chosen_toggles"]["groups"] == {"button#dud 'More'": "revealed no select"}, rep["chosen_toggles"]
    assert "disclosures that revealed no select: accordion 4, groups 1" in band.evidence, band.evidence
    late = [r for r in rep["chosen"] if r["screen"] == "late" and r.get("width") and not r.get("spacing") and r.get("resize_overflow", 0) > 1]
    assert late and all(r["confirmed"] and r["overflow"] <= 1 for r in late), late          # a resize reading, gone when loaded


def test_w58_review_only_a_confirmed_overflow_against_a_fresh_baseline_counts_and_a_box_keeps_its_identity():
    """Batch 14 review S1–S3, on a report: an overflow a fresh load did not confirm is named, never counted; the
    baseline read fresh at confirmation decides over its resize reading; a box a choice relabels is still one box."""
    def row(state, w, **kw):
        return {"screen": "list", "route": "#/list", "state": state, "select": "select#s" if state == "chosen" else None,
                "value": "Long" if state == "chosen" else None, "width": w, "overflow": 0, "midword": [], "spill": [],
                "cut": [], **kw}
    rep = {"reference": None, "scenarios": [], "states": [], "screens": [], "axe": [], "reduced_motion": [], "console": [],
           "requests": [], "timing_ms": [], "forbidden_text": [], "tokens": [], "parity": [], "band_step": 20,
           "reflow_320": [], "band": [], "chosen_widths": [320, 340],
           "chosen": [row("default", 320, overflow=12),                                   # a resize reading only
                      row("default", 340, spill=[{"el": "span.chip", "text": "Showing All", "px": 5}]),
                      row("chosen", 320, overflow=40, confirmed=True, base_overflow=0),   # fresh: the choice's own
                      row("chosen", 340, overflow=9, confirm_error="its longest value could not be chosen on this load",
                          spill=[{"el": "span.chip", "text": "Showing Long", "px": 9}]),
                      {**row("chosen", 320, overflow=0, resize_overflow=30, confirmed=True, base_overflow=0), "select": "select#t"},
                      {**row("chosen", 340, overflow=20), "select": "select#t"},              # its state cleared at 320 px
                      {**row("chosen", 340, overflow=15), "select": "select#u"}]}            # never tried: counts as read
    res = CheckResult()
    browser.findings_from(rep, _thresholds(), res)
    band, text = res.dimensions["RESP-BAND"], res.dimensions["RESP-TEXT"]
    assert [f["message"] for f in band.findings] == ["list overflows the page horizontally at 320 px once select#s shows 'Long'",
                                                     "list overflows the page horizontally at 340 px once select#u shows 'Long'"], band.findings
    assert "list at 340 px once select#t shows 'Long' (a fresh load cleared it at another width)" in band.evidence
    assert "1 overflow reading(s) with a value chosen were past the confirmation cap or time and count as read" in band.evidence
    assert ("overflow with a value chosen not counted: list at 340 px once select#s shows 'Long' (its longest value "
            "could not be chosen on this load)") in band.evidence, band.evidence
    assert not [f for f in text.findings if "span.chip" in f["element"]], text.findings


SNAP_PANES = """<main style="margin:0"><div id="track" style="display:flex;overflow-x:auto;scroll-snap-type:x mandatory">
<section data-screen="list" style="flex:0 0 100%;scroll-snap-align:start"><h1>Signals</h1></section>
<section data-screen="detail" style="flex:0 0 100%;scroll-snap-align:start"><h1>Signal</h1></section></div></main>"""


def test_w58_review_a_pane_that_snaps_sideways_is_not_page_overflow(tmp_path):
    """Batch 14 review R1: a track of full-width panes that snaps sideways (swiped panels) scrolls so on purpose, and N11
    is told so; only a region around the screen that scrolls sideways without snapping is page overflow."""
    from playwright.sync_api import sync_playwright
    entry = _write_html(tmp_path / "p.html", SNAP_PANES, head="<style>body { margin: 0 }</style>")
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 390, "height": 700})
        page.goto(entry.as_uri())
        assert page.evaluate(browser.JS_OVERFLOW) == {"px": 0, "by": ""}
        page.add_style_tag(content="#track { scroll-snap-type: none !important }")
        assert page.evaluate(browser.JS_OVERFLOW) == {"px": 390, "by": "div#track"}
        b.close()


def test_w58_review_the_phone_widths_stop_at_a_phones_width(tmp_path):
    """Batch 14 review N2: a plan whose narrowest width is a desktop's still reads the chosen values at phone widths only."""
    entry = _write_html(tmp_path / "p.html", W58_FILTERS, head="<style>body { font: 14px Arial, sans-serif; margin: 8px; }</style>")
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], [{"id": "list", "route": "#/list", "kind": "list"}], [1280], {**t, "chosen_budget_s": 0},
                            tmp_path / "run")
    assert rep["chosen_widths"][0] == 320 and rep["chosen_widths"][-1] <= 480, rep["chosen_widths"]


R2_26_LISTS = """<main id="app"></main><style>
.list { display: flex; flex-direction: column; background: #FFFFFF; width: 320px }
.row { display: flex; justify-content: space-between; padding: 8px; position: relative; transition: background-color .15s }
.score { padding: 2px 6px } .act { background: #FDE8E1 } .watch { background: #FEF6DA } .monitor { background: #F5F5F5 }
/* the refresh's first list: the chosen row in the alert fill, its score box white, hover in the lowest band's grey */
#bad .row[aria-current="true"] { background: #FDE8E1 } #bad .row[aria-current="true"] .score { background: #FFFFFF }
#bad .row:hover { background: #F5F5F5 }
/* the fix: the rail's bar on a light fill, hover lighter still, every band kept */
#good .row[aria-current="true"] { background: #F0F0F0 } #good .row[aria-current="true"]::before { content: ''; position: absolute;
  left: 0; top: 8px; width: 3px; height: 24px; background: #F40009 } #good .row:not([aria-current="true"]):hover { background: #FAFAFA }
#heavy .row[aria-current="true"] { background: #FAFAFA } #heavy .row:not([aria-current="true"]):hover { background: #E0E0E0 }
/* marked by a class only: its score box takes the row's own fill, and a hovered row's box turns green */
#flip .row.active { background: #F0F0F0 } #flip .row.active .score { background: #F0F0F0 } #flip .row:hover .score { background: #E6F6EC }
/* review I1: cards on a grey page, no hover rule; I2: a translucent list, hover lighter than current */
#flat { background: #F3F4F6 } #flat .row { background: #FFFFFF } #flat .row[aria-current="true"] { background: #EEF4FF }
#veil { background: rgba(0, 0, 0, 0.04) } #veil .row[aria-current="true"] { background: #E0E0E0 }
#veil .row:not([aria-current="true"]):hover { background: #F0F0F0 }
/* review I6: utility classes first; the chosen row's box turns white */
#utility .bg-act { background: #FDE8E1 } #utility .bg-watch { background: #FEF6DA } #utility .bg-monitor { background: #F5F5F5 }
#utility .row[aria-current="true"] span { background: #FFFFFF }
/* review I3: resting rows no pointer reaches, beside a chosen row in the alert fill */
#stuck .row:not([aria-current="true"]) { pointer-events: none } #stuck .row[aria-current="true"] { background: #FDE8E1 }
/* review I3: a rail at the page's top left whose hover is the alert fill: the pointer parked there hovered it */
.rail { position: fixed; top: 0; left: 0; display: flex; flex-direction: column; background: #FFFFFF }
.ri { border: 0; background: #FFFFFF; padding: 4px } .ri.active { background: #D1D1D1 } .ri:not(.active):hover { background: #FDE8E1 }
</style><script>
const rows = (cur, cls, util) => ['act', 'monitor', 'watch', 'monitor'].map((b, i) => '<div class="row' + (i === cur && cls ? ' active"' : '"')
  + (i === cur && !cls ? ' aria-current="true"' : '')
  + ' tabindex="0"><span>Site ' + (i + 1) + '</span><span class="' + (util ? 'bg-' + b + ' score' : 'score ' + b) + '">' + (4 - i)
  + '</span></div>').join('');
function route() { const id = location.hash.slice(2) || 'good';
  document.getElementById('app').innerHTML = '<section data-screen="' + id + '"><h1>Sites</h1><div class="list" id="' + id + '">'
    + rows(0, id === 'flip', id === 'utility') + '</div>' + (id.startsWith('leak') ? '<nav class="rail"><button class="ri">A</button>'
    + '<button class="ri active">B</button><button class="ri">C</button></nav>' : '') + '</section>'; }
route(); window.addEventListener('hashchange', route);
</script>"""


def test_r2_26_an_interactive_state_in_a_status_colour_is_found(tmp_path):
    """Field run 2, R2-26: a list marked its chosen row with the worst score band's own alert fill, turned that row's score
    box white (the band vanished from the row being read) and hovered rows in the lowest band's grey. Every gate passed.
    VIS-STATE-FILLS reads each list's current, resting and hovered items against the design system's status colours and
    the fills its marks vary by, once every transition has finished."""
    entry = _write_html(tmp_path / "p.html", R2_26_LISTS, head="<style>body { font: 14px Arial, sans-serif; margin: 8px; }</style>")
    screens = [{"id": s, "route": f"#/{s}"} for s in ("bad", "good", "heavy", "flip", "flat", "veil", "utility", "stuck",
                                                       "leak1", "leak2")]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 1280], t, tmp_path / "run",
                            status={"red-dim": "#FDE8E1", "amber-dim": "#FEF6DA", "green-dim": "#E6F6EC"})
    res = CheckResult()
    browser.findings_from(rep, t, res)
    dim = res.dimensions["VIS-STATE-FILLS"]
    assert not dim.passed
    got = {(f["location"], f["element"]) for f in dim.findings}
    assert got == {("bad", "div#bad.list > div.row (current fill)"), ("bad", "div#bad.list > div.row (hovered fill)"),
                   ("bad", "div#bad.list > div.row (span@1 when current)"), ("bad", "div#bad.list > div.row (span@1 when hovered)"),
                   ("heavy", "div#heavy.list > div.row (hover heavier)"),
                   ("flip", "div#flip.list > div.row.active (span@1 when current)"),
                   ("flip", "div#flip.list > div.row.active (span@1 when hovered)"),
                   ("utility", "div#utility.list > div.row (span@1 when current)"),              # classes in any order
                   ("stuck", "div#stuck.list > div.row (current fill)"), ("stuck", "div#stuck.list > div.row (span@1 when current)"),
                   ("leak1", "nav.rail > button.ri.active (hovered fill)"),                      # the pointer parked off
                   ("leak2", "nav.rail > button.ri.active (hovered fill)")}, got                 # the page, not on the rail
    msgs = {f["location"] + ": " + f["message"].split(": ", 2)[-1] for f in dim.findings}
    assert "bad: the current item fills rgb(253, 232, 225), the status colour red-dim" in msgs, msgs
    assert "bad: the hovered item fills rgb(245, 245, 245), a colour the list's span marks carry for their data" in msgs, msgs
    assert "bad: span.score.act loses its colour in the current item (rgb(255, 255, 255))" in msgs, msgs
    assert "bad: span.score.monitor takes the hovered item's own fill rgb(245, 245, 245), so its colour vanishes" in msgs, msgs
    assert any(m.startswith("heavy: a hovered item (rgb(224, 224, 224)") for m in msgs), msgs
    assert "flip: span.score.act takes the current item's own fill rgb(240, 240, 240), so its colour vanishes" in msgs, msgs
    assert "flip: span.score.monitor changes its fill from rgb(245, 245, 245) to rgb(230, 246, 236) when its item is hovered" in msgs, msgs
    assert not [f for f in dim.findings if f["location"] in ("good", "flat", "veil")], dim.findings   # review I1, I2
    assert "12 list(s) of items with a current, selected or pressed one read at 1280 px" in dim.evidence, dim.evidence
    assert "stuck div#stuck.list > div.row: not hovered (ElementHandle.hover: Timeout" in dim.evidence, dim.evidence   # review I3


def test_r2_26_the_gate_passes_the_design_systems_status_colours(tmp_path, monkeypatch):
    """The gate's check hands the suite the design system's status colours: a colour whose role or name names a status
    (the field runs' "alert: …", "watch fill", status-green); a surface is none."""
    from types import SimpleNamespace

    from pdg.artifacts import ColorToken
    build = tmp_path / "b"
    build.mkdir()
    (build / "index.html").write_text("<p>x</p>")
    (build / "build-manifest.json").write_text(json.dumps({"entry": "index.html"}))
    colors = [ColorToken(name="red-dim", value="#FDE8E1", role="alert: pill background for held status", provenance="brand",
                         state_fill_of=["sf-btn"]),   # the canon's active filter too (R2-26 addendum)
              ColorToken(name="amber-dim", value="#FEF6DA", role="watch fill, paired with amber-ink", provenance="brand"),
              ColorToken(name="status-green", value="#2F8F48", role="marks beside text", provenance="brand"),
              ColorToken(name="alertRed", value="#D00000", role="x", provenance="brand"),
              ColorToken(name="card", value="#FFFFFF", role="cards, controls, the topbar", provenance="brand"),
              # a status word later in a role, or "band" in a name, names no status (review I4)
              ColorToken(name="surface-2", value="#F5F5F5", role="hover and selected rows; never a status colour", provenance="brand"),
              ColorToken(name="ink", value="#1A1A1A", role="primary text, and the text of status messages", provenance="brand"),
              ColorToken(name="hero-band", value="#EEEEEE", role="the top band behind the page title", provenance="brand")]
    seen: dict = {}

    def fake(*args, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop here")
    monkeypatch.setattr(browser, "run_suite", fake)
    ctx = SimpleNamespace(engine=SimpleNamespace(project=SimpleNamespace(root=tmp_path, config={})), artifact=lambda key: build,
                          work=tmp_path / "w", thresholds={"browser": _thresholds()},
                          state=SimpleNamespace(build=SimpleNamespace(plan=None),
                                                design=SimpleNamespace(screens=[], system=SimpleNamespace(colors=colors))))
    browser.check(ctx)
    assert seen["status"] == {"red-dim": "#FDE8E1", "amber-dim": "#FEF6DA", "status-green": "#2F8F48", "alertRed": "#D00000"}, seen
    assert seen["documented"] == {"red-dim": ["sf-btn"]}, seen


def test_r2_26_one_colour_allows_a_rounding_not_another_colour():
    """A status token written one way computes a unit off another way (an hsl() spelling of it, a transition's last
    frame); a colour 4 or more off in a channel, or with another alpha, is another colour."""
    assert browser._near("rgb(253, 232, 225)", "rgb(252, 233, 226)")
    assert browser._near("rgb(253, 232, 225)", "rgb(250, 232, 225)")
    assert not browser._near("rgb(253, 232, 225)", "rgb(249, 232, 225)")
    assert not browser._near("rgb(253, 232, 225)", "rgba(253, 232, 225, 0.5)")
    assert not browser._near("rgba(0, 0, 0, 0)", "rgba(0, 0, 0, 0)")                   # no fill is no colour


R2_26_DOCUMENTED = """<main data-screen="filters"><h1>Filters</h1>
<div class="filters"><button class="btn btn-sm sf-btn active" aria-pressed="true">All</button><button class="btn btn-sm sf-btn">Open</button>
<button class="btn btn-sm sf-btn">Closed</button></div>
<div class="tabs"><button class="tab active" aria-pressed="true">One</button><button class="tab">Two</button></div>
<div class="chips"><button class="chip sf-btn" aria-pressed="true">All</button><button class="chip">Held</button></div>
<div class="rows"><div class="row" aria-current="true">Lot 0</div><div class="row plain">Lot 1</div><div class="row held">Lot 2</div></div></main>
<style>.sf-btn, .tab, .chip { background: #FFFFFF; border: 1px solid #CCCCCC; padding: 4px 8px }
.sf-btn.active, .tab.active { background: #FDE8E1 } .chip[aria-pressed="true"] { background: #D8D8D8 }
.btn.sf-btn:not(.active):hover { background: #FDE8E1 }
.chip:not([aria-pressed="true"]):hover { background: #FDE8E1 }
.row { padding: 4px 8px; background: #FFFFFF } .row[aria-current="true"] { background: #E0E0E0 } .row.held { background: #FDE8E1 }
.row.plain:hover { background: #FDE8E1 }</style>"""


def test_r2_26_a_state_fill_the_design_system_documents_is_not_judged(tmp_path):
    """Field run 2, R2-26 addendum: the canon fills the active filter button pale red, its alert fill, and says so. The
    check flagged the reference build too, in every unit. A colour now lists the components whose state it fills on
    purpose (`state_fill_of`); their state is named as documented, and every other component's is still judged."""
    from pdg.artifacts import ColorToken
    entry = _write_html(tmp_path / "p.html", R2_26_DOCUMENTED, head="<style>body { font: 14px Arial, sans-serif; margin: 8px; }</style>")
    t = _thresholds()
    # two names for one colour, the documented one first and itself holding " / " (review 2, nits 4 and 14)
    colours = [ColorToken(name="Status / Red", value="#FDE8E1", role="alert fill; the active filter too", provenance="canon",
                          state_fill_of=["sf-btn"]),
               ColorToken(name="pale-red", value="#FDE8E1", role="alert: the same fill, a second name", provenance="canon")]
    screens = [{"id": "filters", "route": ""}]
    always = {"div.tabs > button.tab.active (current fill)",
              "div.chips > button.chip.sf-btn (hovered fill)",     # the hovered sibling is no .sf-btn (review I1)
              "div.rows > div.row (hovered fill)"}                 # a row's data fill is no excuse for a hover (review S6)
    for documented, flagged in ((browser.documented_state_fills(colours), always),
                                ({}, always | {"div.filters > button.btn.btn-sm (current fill)",     # four classes (I2)
                                               "div.filters > button.btn.btn-sm (hovered fill)"})):
        rep = browser.run_suite(entry, [], [], screens, [1280], t, tmp_path / f"run{len(documented)}",
                                status=browser.status_colours(colours), documented=documented)
        res = CheckResult()
        browser.findings_from(rep, t, res)
        dim = res.dimensions["VIS-STATE-FILLS"]
        assert {f["element"] for f in dim.findings} == flagged, dim.findings
        note = ("documented, not judged: filters div.filters > button.btn.btn-sm: Status / Red is the design system's state "
                "fill for .sf-btn; filters div.filters > button.btn.btn-sm when hovered: Status / Red is the design system's "
                "state fill for .sf-btn")
        assert (note in dim.evidence) == bool(documented), dim.evidence


R2_29_LISTS = """<main id="app"></main><script>
// the redraw marks its current row with a state class first ("sel row"): its copy is known by where it sits
const rows = (cur, focusable, id) => ['Site 1', 'Site 2', 'Site 3'].map((t, i) => '<div class="' + (focusable && i === cur ? 'sel ' : '')
  + 'row"' + (focusable ? ' tabindex="0"' : '')
  + (i === cur ? ' aria-current="true"' : '') + ' data-i="' + i + '"><span>' + id + ' ' + t + '</span> <button class="open">Open</button>'
  + '<input class="note" aria-label="Note"></div>').join('');
function route() {
  const id = location.hash.slice(2).split('/')[0] || 'inplace';
  if (id === 'locked' || id === 'firstlocked') {   // a workflow's steps: the later ones disabled until the current is done
    const off = (i) => id === 'locked' ? i > 0 : i === 1;
    document.getElementById('app').innerHTML = '<section data-screen="' + id + '"><h1>Case</h1><div class="steps" role="tablist">'
      + ['Assess', 'Engage', 'Act'].map((t, i) => '<button class="step" role="tab" aria-selected="' + (i === 0) + '"'
        + (off(i) ? ' disabled' : '') + '>' + t + '</button>').join('') + '</div></section>';
    document.querySelector('.steps').addEventListener('click', (e) => { const b = e.target.closest('.step');
      if (b) for (const s of b.parentElement.children) s.setAttribute('aria-selected', String(s === b)); });   // in place
    return;
  }
  if (id === 'nav') {   // navigation links: a click goes to another screen, never judged here
    document.getElementById('app').innerHTML = '<section data-screen="nav"><ul class="menu"><li class="item active"><a href="#/inplace">A</a>'
      + '</li><li class="item"><a href="#/redraw">B</a></li><li class="item"><a href="#/ring">C</a></li></ul></section>';
    return;
  }
  if (id === 'slowbuttons') {
    const buttons = (cur) => ['All', 'Open', 'Closed'].map((t, i) => '<button class="filter' + (i === cur ? ' active' : '')
      + '" aria-pressed="' + (i === cur) + '" data-i="' + i + '">' + t + '</button>').join('');
    document.getElementById('app').innerHTML = '<section data-screen="slowbuttons"><h1>Filters</h1><div class="list filters">'
      + buttons(0) + '</div></section>';
    document.querySelector('.filters').addEventListener('click', (e) => { const b = e.target.closest('.filter');
      if (!b) return; const i = +b.dataset.i; setTimeout(() => { document.querySelector('.filters').innerHTML = buttons(i);
      document.querySelectorAll('.filter')[i].focus(); }, 300); });
    return;
  }
  // a row is 32 px tall, redrawn or not, and the swapfirst detail is one row tall, in the row's box
  document.getElementById('app').innerHTML = '<style>.row { height: 32px }</style><section data-screen="' + id + '"><h1>Sites</h1>'
    + (id === 'below' ? '<div style="height:1400px">Intro</div>' : '') + '<div class="list">'
    + rows(id === 'swapfirst' ? 1 : 0, id === 'redraw' || id === 'below', id) + '</div><h2 id="detail" tabindex="-1">Site</h2></section>';
  const list = document.querySelector('.list');
  list.addEventListener('click', (e) => {
    const row = e.target.closest('.row'); if (!row) return; const i = +row.dataset.i;
    if (id === 'redraw' || id === 'below') { list.innerHTML = rows(i, true, id); list.children[i].focus(); }   // R2-29
    else if (id === 'slowredraw') setTimeout(() => { list.innerHTML = rows(i, true, id); list.children[i].focus(); }, 300);
    else if (id === 'ring') row.querySelector('.open').focus();                             // a control in the list, by script
    else if (id === 'heading') document.getElementById('detail').focus();                   // focus to the detail: a pattern
    else if (id === 'typing') row.querySelector('.note').focus();                           // a text field shows its ring
    else if (id === 'routed') location.hash = '#/inplace';                                  // a row that routes by script
    else if (id === 'swap' || id === 'swapfirst') {   // swapfirst: the first row clicked, a detail one row tall in its box
      list.outerHTML = '<div class="detail" style="height:32px"><h2 tabindex="-1" style="margin:0;font-size:14px">Site ' + (i + 1) + '</h2></div>';
      document.querySelector('.detail h2').focus(); }                                       // a drill-in to the detail
    else for (const r of list.children) r.toggleAttribute('aria-current', r === row);        // updated in place
  });
}
route(); window.addEventListener('hashchange', route);
</script>"""


def test_r2_29_a_click_that_leaves_focus_on_a_redrawn_copy_or_shows_a_ring_is_found(tmp_path):
    """Field run 2, R2-29: a list redrawn on selection put focus back on the new row by script; headless Chromium drew no
    ring, the stakeholder's browser did, and the keyboard focus checks never look at the pointer path. After a click on a
    resting item, focus must be on the node clicked, not a redrawn copy, and nothing may match :focus-visible."""
    entry = _write_html(tmp_path / "p.html", R2_29_LISTS, head="<style>body { font: 14px Arial, sans-serif; margin: 8px; }</style>")
    screens = [{"id": s, "route": f"#/{s}"} for s in ("redraw", "slowredraw", "slowbuttons", "ring", "heading", "typing", "inplace", "nav", "routed",
                                                       "swap", "below", "swapfirst", "locked", "firstlocked")]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 1280], t, tmp_path / "run")
    res = CheckResult()
    browser.findings_from(rep, t, res)
    dim = res.dimensions["A11Y-FOCUS-POINTER"]
    assert {(f["location"], f["element"]) for f in dim.findings} == {
        ("redraw", "div.list > div.sel.row (refocused copy)"), ("ring", "div.list > div.row (ring)"),
        ("slowredraw", "div.list > div.row (refocused copy)"), ("slowredraw", "div.list > div.row (ring)"),
        ("slowbuttons", "div.list.filters > button.filter.active (refocused copy)"),
        ("below", "div.list > div.sel.row (refocused copy)")}, dim.findings                # below the fold too (review S-A)
    # the links are not clicked; a disabled step is passed over for an enabled one, and a list whose other items are all
    # disabled is named, not waited out (refresh field run)
    assert "11 list item(s) clicked at 1280 px" in dim.evidence, dim.evidence
    assert "every other item in the list is disabled" in dim.evidence, dim.evidence
    assert "Timeout" not in dim.evidence, dim.evidence
    assert "1 click(s) went to another screen (not judged)" in dim.evidence, dim.evidence  # the routed row
    assert "div.sel.row in the list matches :focus-visible" in dim.evidence, dim.evidence


R2_26_REVIEW = """<main id="app"></main><style>
.chips { display: flex; gap: 8px; background: #FFFFFF } .chip { height: 32px; border: 0; border-radius: 999px; padding: 0 12px; background: #FFFFFF }
.chip[aria-pressed="true"] { background: #D8D8D8 } .chip:not([aria-pressed="true"]):hover { background: #FDE8E1 }
.navlinks { display: flex; gap: 8px } .navlinks a { padding: 4px } .navlinks a.active { background: #D8D8D8 }
.navlinks a:not(.active):hover { background: #FDE8E1 }
.list { display: flex; flex-direction: column; width: 320px; background: #FFFFFF } .row { display: flex; gap: 8px; padding: 8px }
.act { background: #FDE8E1 } .watch { background: #FEF6DA } .monitor { background: #F5F5F5 } .tag { background: #EEEEEE }
#barfirst .row[aria-current="true"] { background: #F0F0F0 } #barfirst .row[aria-current="true"] .score { background: #FFFFFF }
#optional .row:not([aria-current="true"]):hover { background: #EEEEEE } #optional .row[aria-current="true"] { background: #E0E0E0 }
#redrawing .row[aria-current="true"] { background: #F0F0F0 }
/* review S12: band boxes with one class each, nothing shared; S13: tall cards whose leading pill has its own hover */
#solo .row:not([aria-current="true"]):hover { background: #F5F5F5 } #solo .row[aria-current="true"] { background: #E0E0E0 }
#solo .row[aria-current="true"] span:last-child { background: #FFFFFF }
.card { height: 96px; display: flex; align-items: center; gap: 8px; padding: 0 8px } .card[aria-current="true"] { background: #E0E0E0 }
.card:not([aria-current="true"]):hover { background: #F7F7F7 } .pill { background: #FDE8E1; padding: 0 32px } .pill:hover { background: #FBD0C0 }
</style><script>
const row = (b, i, cur, extra) => '<div class="row"' + (i === cur ? ' aria-current="true"' : '') + '>' + (extra || '') + '<span>Site ' + i
  + '</span><span class="score ' + b + '">' + i + '</span></div>';
const S = {
  pill: '<div class="chips"><button class="chip" aria-pressed="true">All</button><button class="chip">Act</button><button class="chip">Watch</button></div>',
  navlink: '<nav class="navlinks"><a href="#/x" class="active" aria-current="page">Hub</a><a href="#/y">Sites</a><a href="#/z">Cases</a></nav>',
  barfirst: '<div class="list" id="barfirst">' + ['act', 'monitor', 'watch'].map((b, i) => row(b, i, 0, i === 0 ? '<i class="bar">|</i>' : '')).join('') + '</div>',
  optional: '<div class="list" id="optional">' + ['act', 'monitor', 'watch', 'monitor'].map((b, i) => row(b, i, 0, i % 2 ? '<span class="tag">Q3</span>' : '')).join('') + '</div>',
  redrawing: '<div class="list" id="redrawing">' + ['act', 'monitor', 'watch'].map((b, i) => row(b, i, 0)).join('') + '</div>',
  solo: '<div class="list" id="solo">' + ['act', 'monitor', 'watch', 'monitor'].map((b, i) => '<div class="row"'
    + (i === 0 ? ' aria-current="true"' : '') + '><span>Site ' + i + '</span><span class="' + b + '">' + i + '</span></div>').join('') + '</div>',
  mixed: '<div class="list" id="mixed"><div class="row" aria-current="true" style="background:#DBEAFE"><span>Site 0</span></div>'
    + '<div class="row"><span style="background:#DBEAFE" class="kind-a">A</span><span>today</span></div>'
    + '<div class="row"><span style="background:#F3E8FF" class="kind-b">B</span></div></div>',
  tall: '<div class="list" id="tall">' + [0, 1, 2].map((i) => '<div class="card"' + (i === 0 ? ' aria-current="true"' : '')
    + '><span class="pill">Held</span><span>Lot ' + i + '</span></div>').join('') + '</div>',
};
function route() { const id = location.hash.slice(2) || 'pill';
  document.getElementById('app').innerHTML = '<section data-screen="' + id + '"><h1>' + id + '</h1>' + S[id] + '</section>';
  const list = document.getElementById('redrawing');   // rows rebuilt whenever the pointer enters one (review I8)
  if (list) list.addEventListener('mouseover', () => { list.innerHTML = list.innerHTML; }, {once: true});
}
route(); window.addEventListener('hashchange', route);
</script>"""


def test_r2_26_review_round_items_classless_links_a_leading_bar_optional_tags_and_a_redraw(tmp_path):
    """Config batch 5 reviews I7, I8, S8, S9, S10: a fully rounded chip is hovered inside its shape; classless NavLink
    siblings are one list; a current row with a bar in front still pairs its score box; a tag chip only some rows carry is
    no data colour; a list redrawn under the pointer is named, not read as a colour change."""
    entry = _write_html(tmp_path / "p.html", R2_26_REVIEW, head="<style>body { font: 14px Arial, sans-serif; margin: 8px; }</style>")
    screens = [{"id": s, "route": f"#/{s}"} for s in ("pill", "navlink", "barfirst", "optional", "redrawing", "solo", "tall",
                                                       "mixed")]
    t = _thresholds()
    rep = browser.run_suite(entry, [], [], screens, [390, 1280], t, tmp_path / "run",
                            status={"red-dim": "#FDE8E1", "amber-dim": "#FEF6DA"})
    res = CheckResult()
    browser.findings_from(rep, t, res)
    dim = res.dimensions["VIS-STATE-FILLS"]
    assert {(f["location"], f["element"]) for f in dim.findings} == {
        ("pill", "div.chips > button.chip (hovered fill)"), ("navlink", "nav.navlinks > a.active (hovered fill)"),
        ("barfirst", "div#barfirst.list > div.row (span@1 when current)"),                  # paired from the end
        ("solo", "div#solo.list > div.row (hovered fill)"), ("solo", "div#solo.list > div.row (span@1 when current)"),
        ("solo", "div#solo.list > div.row (span@1 when hovered)")}, dim.findings            # the tall cards: nothing
    assert "redrawing div#redrawing.list > div.row: not hovered (redrawn while hovered)" in dim.evidence, dim.evidence

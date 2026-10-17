"""N07–N08: flow coverage, screen reachability, state and keyboard specification."""

from __future__ import annotations

import re
from urllib.parse import unquote

from ..artifacts import ExperienceDoc, InteractionDoc
from ..context import CheckResult, NodeContext

LOCKED = re.compile(r"\b(disabled|locked|greyed|unavailable)\b", re.I)
UNLOCKS = re.compile(r"\b(unlocks? when|enabled when|available when|until)\b", re.I)
# A screen that shows a collection (it can be empty): named or routed as one. The purpose is free text and is not
# read, and a loading state is no signal (a record screen loads too).
DATA_SCREEN = re.compile(r"\b(queue|list|table|log|search|results|history|inbox|feed)s?\b", re.I)
ROUTE_CHAR = r"[\w#/%-]"   # characters a route can continue with: `#/feed` is not `#/feed/regulatory`
ROUTE_END = rf"/?(?!{ROUTE_CHAR}|:\w)"   # an optional trailing slash, then no more route ("#/queue: open lots" ends it)


def _route_core(route: str) -> str:
    return unquote(route.strip()).lstrip("#").rstrip("/")


def _route_pattern(route: str) -> re.Pattern:
    """A route as a whole route. `#/queue` is found in "(#/queue)", "(#/queue/)", "(index.html#/queue)" and, written
    without its `#`, "(/queue)"; not in "(#/queue/L-1)" or "(#/feed/queue)". The root (`#/`, `#` or the bare entry) is
    only `#/` itself, and a route with no `/` needs its `#`, so neither is found in a word of a label."""
    core = _route_core(route)
    if not core:
        return re.compile(rf"#/(?!{ROUTE_CHAR}|:\w)")
    lead = rf"(?:#|(?<!{ROUTE_CHAR}))" if core.startswith(("/", "?")) else "#"
    return re.compile(rf"{lead}{re.escape(core)}{ROUTE_END}")


def _in_navigation(screen, navigation: list[str]) -> bool:
    """The navigation leads to a screen when it names the screen's route as a whole route, or its id in backticks or as
    a whole entry. A word in a label is not an id: "Regulatory signals" does not reach `signal` (W49)."""
    whole_route = _route_pattern(screen.route)
    return any(entry.strip() == screen.id or f"`{screen.id}`" in entry
               or whole_route.search(unquote(entry)) for entry in navigation)


def _drills_down(screen, parent) -> bool:
    """A child reached from its parent without its own navigation entry: a record or form opened from it, or a route
    nested under the parent's. Naming a parent does not make a settings page or a second list reachable (W49 review)."""
    if screen.kind in ("record", "form"):
        return True
    base = _route_core(parent.route)
    return bool(base) and _route_core(screen.route).startswith(base + "/")


def check_flows(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = ExperienceDoc.model_validate(ctx.json("experience"))
    p0 = {r.id for r in ctx.state.product.requirements if r.priority == "P0"}
    covered = {rid for f in doc.flows for rid in f.requirement_ids}
    uncovered = sorted(p0 - covered)
    incomplete = [f.id for f in doc.flows if not f.steps or not f.entry or not f.exit]
    res.dim("EXP-COVERAGE", not uncovered and not incomplete and bool(doc.flows),
            f"{len(p0) - len(uncovered)}/{len(p0)} P0 requirements covered by {len(doc.flows)} flows"
            + (f"; uncovered {uncovered}" if uncovered else "") + (f"; incomplete flows {incomplete}" if incomplete else ""))
    screens = {s.id for s in doc.screens}
    routes = [s.route for s in doc.screens]
    unknown = sorted({st.screen for f in doc.flows for st in f.steps} | {f.entry for f in doc.flows} |
                     {f.exit for f in doc.flows}) 
    unknown = [s for s in unknown if s not in screens]
    used = {st.screen for f in doc.flows for st in f.steps} | {f.entry for f in doc.flows} | {f.exit for f in doc.flows}
    reached = used | {s.id for s in doc.screens if _in_navigation(s, doc.navigation)}
    by_id = {s.id: s for s in doc.screens}
    parents = {s.id: s.parent for s in doc.screens if s.parent in by_id and _drills_down(s, by_id[s.parent])}
    via_parent: list[str] = []
    while grown := {c for c, p in parents.items() if p in reached} - reached:   # a drill-down of a reachable screen
        reached |= grown
        via_parent += [f"{c} ← {parents[c]}" for c in sorted(grown)]
    orphans = [s.id for s in doc.screens if s.id not in reached]
    dup = sorted({r for r in routes if routes.count(r) > 1})
    unkinded = [s.id for s in doc.screens if not s.kind]   # N08's state coverage relies on it (a list can be empty)
    res.dim("EXP-SCREENS", not unknown and not orphans and not dup and not unkinded,
            f"{len(screens)} screens" + (f"; unknown in flows {unknown}" if unknown else "")
            + (f"; orphan screens {orphans} (reachable means a flow uses it, the navigation names its route, e.g. "
               f"'Queue (#/queue)', or its id in backticks, or it is a record, a form or a nested route under a "
               f"reachable parent)" if orphans else "")
            + (f"; reached only through its parent: {', '.join(via_parent)}" if via_parent else "")
            + (f"; duplicate routes {dup}" if dup else "")
            + (f"; screens without a kind (list · record · form · dashboard · other) {unkinded}" if unkinded else ""))
    return res


def check_interactions(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = InteractionDoc.model_validate(ctx.json("interactions"))
    screens = {s.id for s in ctx.state.design.screens}
    design_screens = {s.id: s for s in ctx.state.design.screens}
    specs = {s.screen: s for s in doc.screens}
    missing = sorted(screens - set(specs))

    def is_data_screen(spec) -> bool:
        screen = design_screens.get(spec.screen)
        if "empty" in spec.states:
            return True
        if screen is not None and screen.kind:   # a declared kind decides; the name is only a fallback
            return screen.kind == "list"
        text = " ".join([spec.screen, *(screen and [screen.name, screen.route.replace("/", " ")] or [])])
        return bool(DATA_SCREEN.search(text))

    data_without_empty = [s.screen for s in specs.values() if is_data_screen(s) and "empty" not in s.states]
    data_without_error = [s.screen for s in specs.values() if is_data_screen(s) and "error" not in s.states]
    records_without_error = [s.screen for s in specs.values() if not is_data_screen(s) and "error" not in s.states]
    no_success = [s.screen for s in specs.values() if "success" not in s.states and "default" not in s.states]
    res.dim("EXP-STATES", not (missing or data_without_empty or data_without_error or records_without_error or no_success),
            f"{len(specs)} screen specs" + (f"; missing specs {missing}" if missing else "")
            + (f"; data screens without an empty state {data_without_empty}" if data_without_empty else "")
            + (f"; data screens without an error state {data_without_error}" if data_without_error else "")
            + (f"; screens without an error state {records_without_error}" if records_without_error else "")
            + (f"; screens without a success/default state {no_success}" if no_success else ""))
    no_kb = [f"{s.screen}:{i.id}" for s in specs.values() for i in s.interactions if not i.keyboard.strip()]
    res.dim("EXP-KEYBOARD", not no_kb and bool(doc.focus_rules), f"interactions without keyboard behaviour: {no_kb or 'none'}; "
            f"{len(doc.focus_rules)} focus rules")
    unexplained = [f"{s.screen}:{i.id}" for s in specs.values() for i in s.interactions
                   if LOCKED.search(i.response + " " + i.feedback) and not UNLOCKS.search(i.response + " " + i.feedback)]
    res.dim("EXP-LOCKED-EXPLAINED", not unexplained, f"locked actions without an 'unlocks when' reason: {unexplained or 'none'}")
    return res

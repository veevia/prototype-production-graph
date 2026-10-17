/* Lot Release Workbench — UI (fictional example for the pdg workflow).
 * Vanilla JS, no network: data is inlined at build time (#lots-data). Decisions and drafts persist in localStorage.
 * Test affordances (documented in controls/prototype.md): ?fail=1 simulates a failed first load of the queue;
 * ?loading=hold keeps the queue in its loading state; ?storage=off simulates unavailable browser storage;
 * ?log=empty hides the previous shift's decisions (a first-day plant); #/queue?q=<text> pre-fills the search.
 */
(function () {
  "use strict";
  var D = window.LotDomain;
  var DATA = JSON.parse(document.getElementById("lots-data").textContent);
  var params = new URLSearchParams(location.search);
  var sim = { failOnce: params.get("fail") === "1", holdLoading: params.get("loading") === "hold",
              storageOff: params.get("storage") === "off", logEmpty: params.get("log") === "empty" };
  var HISTORY = sim.logEmpty ? [] : (DATA.history || []).slice().sort(function (a, b) { return b.at.localeCompare(a.at); });
  var STORE_KEY = "lot-release-workbench/v1";
  var REVIEWER = "Morgan Lee";
  var app = document.getElementById("app");
  var live = document.getElementById("live");
  var ui = { filter: "all", q: "", loaded: false, error: false };
  var storageOk = true; // must be set before loadStore() runs: loadStore() may turn it off
  var store = loadStore();
  var firstRender = true;
  var lastHash = null;

  var specs = DATA.specs;
  var suppliers = {};
  DATA.suppliers.forEach(function (s) { suppliers[s.id] = s; });
  var lots = DATA.lots.map(function (lot) {
    var spec = specs[lot.material];
    var evaluated = D.evaluateLot(lot, spec);
    return { lot: lot, spec: spec, supplier: suppliers[lot.supplier], evaluated: evaluated, verdict: D.verdict(evaluated) };
  });
  var byId = {};
  lots.forEach(function (x) { byId[x.lot.id] = x; });

  var ICON = {
    ready: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M6.2 11.3 3 8.1l1.1-1.1 2.1 2.1 5.6-5.6L12.9 4.6z"/></svg>',
    hold: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M5 3h2v10H5zm4 0h2v10H9z"/></svg>',
    escalate: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 2 15 14H1zm-.8 4v4h1.6V6zm0 5v1.6h1.6V11z"/></svg>',
    within: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M6.2 11.3 3 8.1l1.1-1.1 2.1 2.1 5.6-5.6L12.9 4.6z"/></svg>',
    borderline: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 1.5a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13zm-.8 3v4.3h1.6V4.5zm0 5.3v1.7h1.6V9.8z"/></svg>',
    out: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m4.1 3 3.9 3.9L11.9 3 13 4.1 9.1 8l3.9 3.9-1.1 1.1L8 9.1 4.1 13 3 11.9 6.9 8 3 4.1z"/></svg>',
    missing: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 2 15 14H1zm-.8 4v4h1.6V6zm0 5v1.6h1.6V11z"/></svg>'
  };
  var RESULT_LABEL = { within: "Within", borderline: "Borderline", out: "Out of spec", missing: "Missing" };

  // ---------------------------------------------------------------------------------------------- store
  function freshStore() { return { decisions: {}, notices: {}, log: [] }; }
  function loadStore() {
    try {
      if (sim.storageOff) throw new Error("storage disabled (simulated)");
      return JSON.parse(localStorage.getItem(STORE_KEY)) || freshStore();
    } catch (e) { storageOk = false; return freshStore(); }
  }
  function saveStore() {
    if (!storageOk) return;
    try { localStorage.setItem(STORE_KEY, JSON.stringify(store)); } catch (e) { storageOk = false; }
  }
  function storageWarning() {
    return storageOk ? "" : '<div class="state state--error state--inline" data-state="error" role="alert"><h2 class="state__title">' +
      "Decisions can't be saved in this browser</h2><p>Storage is unavailable, so decisions last only until you close this tab. " +
      "Record them in the paper log as well.</p></div>";
  }

  // ---------------------------------------------------------------------------------------------- helpers
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function announce(msg) { live.textContent = ""; window.setTimeout(function () { live.textContent = msg; }, 40); }
  function when(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }) + " " +
           d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }
  function day(s) { return new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short" }); }
  function nb(s) { return String(s).replace(/ (?=°|%)/g, "\u00a0"); }
  function statusOf(id) { return D.lotStatus(store.decisions[id]); }
  function chip(kind, label) { return '<span class="chip chip--' + kind + '">' + (ICON[kind] || "") + esc(label) + "</span>"; }

  function parseRoute() {
    var h = (location.hash || "#/queue").slice(1);
    var parts = h.split("?");
    var path = parts[0];
    var query = new URLSearchParams(parts[1] || "");
    var m;
    if ((m = path.match(/^\/lot\/([^/]+)\/notice$/))) return { screen: "notice", id: decodeURIComponent(m[1]), query: query };
    if ((m = path.match(/^\/lot\/([^/]+)$/))) return { screen: "lot", id: decodeURIComponent(m[1]), query: query };
    if (path === "/audit") return { screen: "audit", query: query };
    return { screen: "queue", query: query };
  }

  // ---------------------------------------------------------------------------------------------- queue
  var FILTERS = [["all", "All"], ["needs-review", "Needs review"], ["on-hold", "On hold"], ["released", "Released"], ["rejected", "Rejected"]];

  function visibleLots() {
    var q = ui.q.trim().toLowerCase();
    return lots.filter(function (x) {
      var st = statusOf(x.lot.id).id;
      if (ui.filter !== "all" && st !== ui.filter) return false;
      if (!q) return true;
      return [x.lot.id, x.lot.coa, x.spec.material, x.supplier.name].join(" ").toLowerCase().indexOf(q) >= 0;
    }).sort(function (a, b) {
      var ra = statusOf(a.lot.id).id === "needs-review" ? 0 : 1;
      var rb = statusOf(b.lot.id).id === "needs-review" ? 0 : 1;
      return ra - rb || b.verdict.tier - a.verdict.tier || a.lot.due.localeCompare(b.lot.due) || a.lot.id.localeCompare(b.lot.id);
    });
  }

  function renderQueue(route) {
    var counts = {};
    FILTERS.forEach(function (f) { counts[f[0]] = 0; });
    lots.forEach(function (x) { counts.all++; counts[statusOf(x.lot.id).id]++; });
    var head = '<div class="page-head"><h1 id="screen-title" tabindex="-1">Lot queue</h1>' +
      '<p class="lede">Incoming ingredient lots with their supplier certificates of analysis. The verdict is derived from ' +
      "each certificate against its specification; the decision is yours.</p></div>";
    var ready = ui.loaded && !ui.error;   // no counts or filtering while there is no list to count or filter
    var tools = '<div class="toolbar"><div class="filters" role="group" aria-label="Filter lots by status">' +
      FILTERS.map(function (f) {
        return '<button type="button" class="filter" data-filter="' + f[0] + '" aria-pressed="' + (ui.filter === f[0]) + '"' +
               (ready ? "" : " disabled") + ">" + esc(f[1]) + (ready ? ' <span class="count">' + counts[f[0]] + "</span>" : "") + "</button>";
      }).join("") + '</div><div class="search"><label for="search">Search</label>' +
      '<input id="search" type="search" autocomplete="off" placeholder="Lot, certificate, material or supplier" value="' + esc(ui.q) + '"' +
      (ready ? "" : " disabled") + "></div></div>";
    var body;
    if (!ui.loaded) {
      body = '<div class="state" data-state="loading" aria-busy="true"><p class="state__title">Loading lots…</p>' +
             '<div class="skeleton" aria-hidden="true"><span></span><span></span><span></span></div></div>';
    } else if (ui.error) {
      body = '<div class="state state--error" data-state="error" role="alert"><h2 class="state__title">The lot list did not load</h2>' +
             "<p>The plant server did not answer (simulated). Nothing you recorded was lost.</p>" +
             '<button type="button" class="btn btn--primary" data-testid="retry">Try again</button></div>';
    } else {
      var rows = visibleLots();
      if (!rows.length) {
        body = '<div class="state" data-state="empty"><h2 class="state__title">No lots match</h2><p>Nothing matches ' +
               (ui.q ? "“" + esc(ui.q) + "”" : "this filter") + (ui.filter !== "all" ? " in " + esc(FILTERS.filter(function (f) { return f[0] === ui.filter; })[0][1]) : "") +
               '.</p><button type="button" class="btn" data-testid="reset-filters">Reset filters</button></div>';
      } else {
        body = '<div class="table-region"><table class="data-table queue-table" data-testid="queue-table">' +
          '<caption class="sr-only">Lots with their derived verdict and decision status</caption>' +
          '<thead><tr><th scope="col">Lot</th><th scope="col">Material</th><th scope="col">Supplier</th>' +
          '<th scope="col">Received</th><th scope="col">Verdict</th><th scope="col">Status</th></tr></thead><tbody>' +
          rows.map(function (x) {
            var st = statusOf(x.lot.id);
            return '<tr data-lot-row="' + esc(x.lot.id) + '">' +
              '<td data-label="Lot"><span class="cell-stack"><a class="lot-link" href="#/lot/' + esc(x.lot.id) + '" data-lot-link="' +
              esc(x.lot.id) + '">' + esc(x.lot.id) + '</a><span class="sub sub--id">' + esc(x.lot.coa) + "</span></span></td>" +
              '<td data-label="Material">' + esc(nb(x.spec.material)) + "</td>" +
              '<td data-label="Supplier">' + esc(x.supplier.name) + "</td>" +
              '<td data-label="Received"><time datetime="' + esc(x.lot.received) + '">' + day(x.lot.received) + "</time></td>" +
              '<td data-label="Verdict">' + chip(x.verdict.id, x.verdict.label) + "</td>" +
              '<td data-label="Status">' + chip("status", st.label) + "</td></tr>";
          }).join("") + "</tbody></table></div>" +
          '<p class="table-note">Showing ' + rows.length + " of " + lots.length + " lots · needs review first, then by verdict " +
          "(escalate, hold, ready) and review due date.</p>";
      }
    }
    return '<section data-screen="queue" aria-labelledby="screen-title">' + head + storageWarning() + tools + body + "</section>";
  }

  // ---------------------------------------------------------------------------------------------- lot
  function crumbs(items) {
    return '<nav class="crumbs" aria-label="Breadcrumb"><ol>' + items.map(function (it, i) {
      return "<li>" + (it[1] ? '<a href="' + it[1] + '">' + esc(it[0]) + "</a>" : '<span aria-current="page">' + esc(it[0]) + "</span>") + "</li>";
    }).join("") + "</ol></nav>";
  }

  function notFound(screen, id) {
    return '<section data-screen="' + screen + '" aria-labelledby="screen-title">' + crumbs([["Lot queue", "#/queue"], [id, null]]) +
      '<div class="state state--error" data-state="error"><h1 id="screen-title" tabindex="-1">Lot ' + esc(id) + " was not found</h1>" +
      "<p>It is not in this plant's queue. Check the lot number on the delivery note.</p>" +
      '<a class="btn btn--primary" href="#/queue">Back to the lot queue</a></div></section>';
  }

  function renderLot(route) {
    var x = byId[route.id];
    if (!x) return notFound("lot", route.id);
    var lot = x.lot;
    var decided = store.decisions[lot.id];
    var v = x.verdict;
    var meta = [["Supplier", x.supplier.name], ["Received", day(lot.received)], ["Review due", day(lot.due)],
                ["Purchase order", lot.po], ["Certificate", lot.coa]];
    var head = crumbs([["Lot queue", "#/queue"], [lot.id, null]]) + '<div class="page-head"><h1 id="screen-title" tabindex="-1">Lot ' +
      esc(lot.id) + ' <span class="title-sub">' + esc(nb(x.spec.material)) + '</span></h1><dl class="meta">' +
      meta.map(function (m) { return "<div><dt>" + esc(m[0]) + "</dt><dd>" + esc(m[1]) + "</dd></div>"; }).join("") + "</dl></div>";
    var verdictBox = '<div class="verdict verdict--' + v.id + '" data-testid="verdict"><p class="verdict__label">' + ICON[v.id] +
      "<span>Derived verdict: <strong>" + esc(v.label) + "</strong></span></p>" +
      '<p class="verdict__reason">' + esc(v.reason) + ".</p>" +
      '<p class="verdict__rule">Any out-of-spec result → Hold. Any missing or unreadable result → Escalate (missing data never lowers the tier). Otherwise → Ready. You make the decision.</p></div>';
    var table = '<section class="comparison" aria-labelledby="cmp-title"><h2 id="cmp-title">Certificate results against specification</h2>' +
      '<div class="table-region"><table class="data-table comparison-table" data-testid="comparison-table">' +
      '<caption class="sr-only">Each certificate result compared with its specification limit</caption>' +
      '<thead><tr><th scope="col">Parameter</th><th scope="col">Specification</th><th scope="col">Certificate</th>' +
      '<th scope="col">Result</th><th scope="col">How it was derived</th></tr></thead><tbody>' +
      x.evaluated.map(function (r) {
        return "<tr><th scope=\"row\" data-label=\"Parameter\">" + esc(r.name) + '</th><td data-label="Specification">' + esc(r.spec) +
          '</td><td data-label="Certificate" class="num">' + (r.value === null ? "<em>not readable</em>" : esc(D.fmt(r.value, r.unit))) +
          '</td><td data-label="Result">' + chip(r.status, RESULT_LABEL[r.status]) + '</td><td data-label="How it was derived" class="derivation">' +
          '<span class="cell-stack">' + esc(r.derivation) + (r.note ? '<span class="sub">' + esc(r.note) + "</span>" : "") + "</span></td></tr>";
      }).join("") + "</tbody></table></div></section>";
    var panel;
    if (decided) {
      var st = D.lotStatus(decided);
      panel = '<section class="decision-panel" aria-labelledby="dec-title"><h2 id="dec-title">Verdict and decision</h2>' + verdictBox +
        '<p class="decision-status" data-testid="decision-status" role="status">' + chip("status", st.label) + " " +
        esc(st.label) + " by " + esc(decided.by) + " at " + esc(when(decided.at)) + ".</p>" +
        (decided.rationale ? '<blockquote class="rationale">' + esc(decided.rationale) + "</blockquote>" : "") +
        '<p class="panel-links"><a href="#/audit">See it in the decision log</a>' +
        (decided.decision !== "release" ? ' · <a data-testid="draft-notice" href="#/lot/' + esc(lot.id) + '/notice">Draft supplier notice</a>' : "") +
        "</p></section>";
    } else {
      var locked = !D.canRelease(v);
      panel = '<section class="decision-panel" aria-labelledby="dec-title"><h2 id="dec-title">Verdict and decision</h2>' + verdictBox +
        '<form data-testid="decision-form" novalidate><fieldset><legend>Choose a decision</legend>' +
        '<label class="option' + (locked ? " option--locked" : "") + '"><input type="radio" name="decision" id="decision-release" value="release"' +
        (locked ? ' disabled aria-describedby="release-hint"' : "") + "> Release</label>" +
        (locked ? '<p class="hint" id="release-hint" data-testid="release-hint">Release unlocks when every result is within specification.</p>' : "") +
        '<label class="option"><input type="radio" name="decision" id="decision-hold" value="hold"> Hold</label>' +
        '<label class="option"><input type="radio" name="decision" id="decision-reject" value="reject"> Reject</label>' +
        '<p class="field-error" id="decision-error" data-testid="decision-error"></p></fieldset>' +
        '<label for="rationale" class="field-label">Rationale <span class="hint">required for hold and reject — at least ' + D.MIN_RATIONALE + " characters</span></label>" +
        '<textarea id="rationale" rows="4" aria-describedby="rationale-count rationale-error"></textarea>' +
        '<p class="hint" id="rationale-count">0 characters</p>' +
        '<p class="field-error" id="rationale-error" data-testid="rationale-error"></p>' +
        '<button type="submit" class="btn btn--primary" data-testid="record-decision">Record decision</button></form>' +
        '<p class="decision-status" data-testid="decision-status" role="status"></p></section>';
    }
    return '<section data-screen="lot" aria-labelledby="screen-title">' + head +
      '<div class="lot-layout">' + table + '<div class="decision-col">' + storageWarning() + panel + "</div></div></section>";
  }

  // ---------------------------------------------------------------------------------------------- notice
  function renderNotice(route) {
    var x = byId[route.id];
    if (!x) return notFound("notice", route.id);
    var head = crumbs([["Lot queue", "#/queue"], [x.lot.id, "#/lot/" + encodeURIComponent(x.lot.id)], ["Supplier notice", null]]);
    if (D.canRelease(x.verdict)) {
      return '<section data-screen="notice" aria-labelledby="screen-title">' + head +
        '<div class="state" data-state="not-needed"><h1 id="screen-title" tabindex="-1">No notice needed for ' + esc(x.lot.id) + "</h1>" +
        "<p>Every result on certificate " + esc(x.lot.coa) + " is within specification.</p>" +
        '<a class="btn" href="#/lot/' + esc(x.lot.id) + '">Back to the lot</a></div></section>';
    }
    var decided = store.decisions[x.lot.id];
    var draft = D.noticeDraft(x.lot, x.spec.material, x.supplier, x.evaluated, decided);
    var saved = store.notices[x.lot.id];
    var decLine = '<p class="notice-decision" data-testid="notice-decision">' + (decided
      ? chip("status", D.lotStatus(decided).label) + " " + esc(D.lotStatus(decided).label) + " by " + esc(decided.by) + " at " + esc(when(decided.at)) + "."
      : "No decision recorded for this lot yet.") + "</p>";
    return '<section data-screen="notice" aria-labelledby="screen-title">' + head +
      '<div class="page-head"><h1 id="screen-title" tabindex="-1">Supplier notice draft · ' + esc(x.lot.id) + "</h1>" + decLine + "</div>" + storageWarning() +
      '<p class="banner" role="note"><strong>Draft only.</strong> Sending happens outside this prototype; nothing leaves this page.</p>' +
      '<div class="notice-layout"><section aria-labelledby="issues-title"><h2 id="issues-title">What needs the supplier’s action</h2>' +
      '<ul class="issues" data-testid="notice-issues">' + draft.issues.map(function (r) {
        return "<li>" + chip(r.status, RESULT_LABEL[r.status]) + " <strong>" + esc(r.name) + "</strong>: " +
          (r.value === null ? "no readable value" : esc(D.fmt(r.value, r.unit))) + " (specification " + esc(r.spec) + ")</li>";
      }).join("") + "</ul></section>" +
      '<section aria-labelledby="text-title"><h2 id="text-title">Notice text</h2><textarea id="notice-body" rows="12" aria-labelledby="text-title">' +
      esc(saved ? saved.text : draft.text) + "</textarea>" +
      '<div class="actions"><button type="button" class="btn btn--primary" data-testid="save-draft">Save draft</button>' +
      '<a class="btn" href="#/lot/' + esc(x.lot.id) + '">Back to the lot</a></div>' +
      '<p class="decision-status" data-testid="notice-status" role="status">' +
      (saved ? "Draft saved — not sent (" + esc(when(saved.at)) + ")." : "") + "</p></section></div></section>";
  }

  // ---------------------------------------------------------------------------------------------- audit
  var DECISION_LABEL = { release: "Released", hold: "On hold", reject: "Rejected" };

  function renderAudit() {
    var head = '<div class="page-head"><h1 id="screen-title" tabindex="-1">Decision log</h1><p class="lede">Every decision, who made it, ' +
      "when, and the derived verdict at that moment. Newest first.</p></div>";
    var rows = store.log.slice().reverse().concat(HISTORY);
    if (!rows.length) {
      return '<section data-screen="audit" aria-labelledby="screen-title">' + head + storageWarning() +
        '<div class="state" data-state="empty"><h2 class="state__title">No decisions recorded yet</h2>' +
        "<p>Decisions you record on a lot appear here with their rationale.</p>" +
        '<a class="btn btn--primary" href="#/queue">Go to the lot queue</a></div></section>';
    }
    return '<section data-screen="audit" aria-labelledby="screen-title">' + head + storageWarning() +
      '<div class="table-region"><table class="data-table audit-table" data-testid="audit-table">' +
      '<caption class="sr-only">Recorded decisions, newest first</caption><thead><tr><th scope="col">Time</th>' +
      '<th scope="col">Lot</th><th scope="col">Decision</th><th scope="col">Verdict at decision</th>' +
      '<th scope="col">Rationale</th><th scope="col">Reviewer</th></tr></thead><tbody>' +
      rows.map(function (e) {
        return '<tr><td data-label="Time"><time datetime="' + esc(e.at) + '">' + esc(when(e.at)) + "</time></td>" +
          '<td data-label="Lot">' + (byId[e.lot] ? '<a class="lot-link" href="#/lot/' + esc(e.lot) + '">' + esc(e.lot) + "</a>"
            : '<span class="cell-stack"><span class="lot-id">' + esc(e.lot) + '</span><span class="sub">Previous shift</span></span>') + "</td>" +
          '<td data-label="Decision">' + chip("status", DECISION_LABEL[e.decision]) + "</td>" +
          '<td data-label="Verdict at decision">' + chip(e.verdict, e.verdictLabel) + "</td>" +
          '<td data-label="Rationale">' + (e.rationale ? esc(e.rationale) : "<em>none given</em>") + "</td>" +
          '<td data-label="Reviewer">' + esc(e.by) + "</td></tr>";
      }).join("") + "</tbody></table></div>" +
      (HISTORY.length ? '<p class="table-note">' + store.log.length + " decision" + (store.log.length === 1 ? "" : "s") +
        " this session · " + HISTORY.length + " from the previous shift (synthetic).</p>" : "") + "</section>";
  }

  // ---------------------------------------------------------------------------------------------- render & events
  function addTableRoles(t) {
    // Phones restack tables with CSS display rules, which drop native table semantics; explicit roles keep them.
    t.setAttribute("role", "table");
    t.querySelectorAll("thead, tbody").forEach(function (g) { g.setAttribute("role", "rowgroup"); });
    t.querySelectorAll("tr").forEach(function (r) { r.setAttribute("role", "row"); });
    t.querySelectorAll("thead th").forEach(function (c) { c.setAttribute("role", "columnheader"); });
    t.querySelectorAll("tbody th").forEach(function (c) { c.setAttribute("role", "rowheader"); });
    t.querySelectorAll("td").forEach(function (c) { c.setAttribute("role", "cell"); });
  }

  function ensureLoaded() {
    if (ui.loaded || sim.holdLoading) return;
    window.setTimeout(function () {
      ui.loaded = true;
      ui.error = sim.failOnce;
      sim.failOnce = false;
      render();
      if (ui.error) announce("The lot list did not load. Use Try again.");
    }, 150);
  }

  function render() {
    var route = parseRoute();
    if (location.hash !== lastHash) {
      lastHash = location.hash;
      if (route.screen === "queue" && route.query.get("q") !== null) ui.q = route.query.get("q");
    }
    var html = route.screen === "lot" ? renderLot(route) : route.screen === "notice" ? renderNotice(route)
      : route.screen === "audit" ? renderAudit() : renderQueue(route);
    app.innerHTML = html;
    app.querySelectorAll("table.data-table").forEach(addTableRoles);
    document.querySelectorAll("[data-nav]").forEach(function (a) {
      var on = a.getAttribute("data-nav") === (route.screen === "audit" ? "audit" : "queue");
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    var note = document.querySelector("[data-storage-note]");
    if (note) note.textContent = storageOk ? "Decisions are stored in this browser only."
      : "Decisions are not being saved: storage is unavailable in this browser.";
    var title = document.getElementById("screen-title");
    document.title = (title ? title.textContent.replace(/\s+/g, " ").trim() + " — " : "") + "Lot Release Workbench (fictional)";
    if (route.screen === "queue") ensureLoaded();
    if (!firstRender && title) title.focus();
    firstRender = false;
  }

  function onSubmit(form) {
    var route = parseRoute();
    var x = byId[route.id];
    var choice = form.querySelector('input[name="decision"]:checked');
    var decision = choice ? choice.value : "";
    var rationale = document.getElementById("rationale").value;
    var errors = D.validateDecision(decision, rationale, x.verdict);
    var decErr = document.getElementById("decision-error");
    var ratErr = document.getElementById("rationale-error");
    decErr.textContent = "";
    ratErr.textContent = "";
    document.getElementById("rationale").removeAttribute("aria-invalid");
    if (errors.length) {
      errors.forEach(function (e) { (e.field === "rationale" ? ratErr : decErr).textContent = e.message; });
      if (errors[0].field === "rationale") {
        var ta = document.getElementById("rationale");
        ta.setAttribute("aria-invalid", "true");
        ta.focus();
      } else {
        (form.querySelector('input[name="decision"]:not([disabled])') || form).focus();
      }
      return;
    }
    var entry = { lot: x.lot.id, decision: decision, rationale: rationale.trim(), verdict: x.verdict.id,
                  verdictLabel: x.verdict.label, by: REVIEWER, at: new Date().toISOString() };
    store.decisions[x.lot.id] = entry;
    store.log.push(entry);
    saveStore();
    render();
    announce("Decision recorded: lot " + x.lot.id + " " + DECISION_LABEL[decision].toLowerCase() + ".");
  }

  app.addEventListener("click", function (ev) {
    var t = ev.target.closest("button, a");
    if (!t) return;
    if (t.hasAttribute("data-filter")) {
      ui.filter = t.getAttribute("data-filter");
      render();
      var again = app.querySelector('[data-filter="' + ui.filter + '"]');
      if (again && ev.detail === 0) again.focus();
      announce(app.querySelector(".table-note") ? app.querySelector(".table-note").textContent : "No lots match.");
    } else if (t.getAttribute("data-testid") === "retry") {
      ui.loaded = false;
      ui.error = false;
      render();
    } else if (t.getAttribute("data-testid") === "reset-filters") {
      ui.filter = "all";
      ui.q = "";
      render();
      var s = document.getElementById("search");
      if (s) s.focus();
      announce("Filters reset. Showing all " + lots.length + " lots.");
    } else if (t.getAttribute("data-testid") === "save-draft") {
      var id = parseRoute().id;
      store.notices[id] = { text: document.getElementById("notice-body").value, at: new Date().toISOString() };
      saveStore();
      var ns = document.querySelector('[data-testid="notice-status"]');
      ns.textContent = "Draft saved — not sent (" + when(store.notices[id].at) + ").";
    }
  });

  app.addEventListener("input", function (ev) {
    if (ev.target.id === "search") {
      ui.q = ev.target.value;
      var pos = ev.target.selectionStart;
      render();
      var s = document.getElementById("search");
      if (s) { s.focus(); try { s.setSelectionRange(pos, pos); } catch (e) { /* type=search may refuse */ } }
    } else if (ev.target.id === "rationale") {
      document.getElementById("rationale-count").textContent = ev.target.value.trim().length + " characters";
    }
  });

  app.addEventListener("submit", function (ev) {
    ev.preventDefault();
    onSubmit(ev.target);
  });

  document.querySelector('[data-testid="reset-demo"]').addEventListener("click", function () {
    var n = store.log.length + Object.keys(store.notices).length;
    if (n && !window.confirm("Erase " + store.log.length + " recorded decision(s) and " + Object.keys(store.notices).length +
                             " saved notice draft(s) from this browser? This cannot be undone.")) return;
    store = freshStore();
    saveStore();
    render();
    announce("Demo data reset: no decisions recorded.");
  });

  var build = document.querySelector("[data-build]");
  if (build) build.textContent = DATA.build || "dev";
  window.addEventListener("hashchange", render);
  render();
})();

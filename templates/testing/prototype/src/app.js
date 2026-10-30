/* Workflow test harness — UI (technical fixture for the pdg workflow).
 * Vanilla JS, no network: data is inlined at build time (#records-data). Decisions and drafts persist in localStorage.
 * Test affordances (documented in controls/prototype.md): ?fail=1 simulates a failed first load of the queue;
 * ?loading=hold keeps the queue in its loading state; ?storage=off simulates unavailable browser storage;
 * ?log=empty hides the previous test run's decisions (a new test run); #/queue?q=<text> pre-fills the search.
 */
(function () {
  "use strict";
  var D = window.RecordRules;
  var DATA = JSON.parse(document.getElementById("records-data").textContent);
  var params = new URLSearchParams(location.search);
  var sim = { failOnce: params.get("fail") === "1", holdLoading: params.get("loading") === "hold",
              storageOff: params.get("storage") === "off", logEmpty: params.get("log") === "empty" };
  var HISTORY = sim.logEmpty ? [] : (DATA.history || []).slice().sort(function (a, b) { return b.at.localeCompare(a.at); });
  var STORE_KEY = "workflow-test-harness/v1";
  var REVIEWER = "Test actor A";
  var app = document.getElementById("app");
  var live = document.getElementById("live");
  var ui = { filter: "all", q: "", loaded: false, error: false };
  var storageOk = true; // must be set before loadStore() runs: loadStore() may turn it off
  var store = loadStore();
  var firstRender = true;
  var lastHash = null;

  var specs = DATA.specs;
  var sources = {};
  DATA.sources.forEach(function (s) { sources[s.id] = s; });
  var records = DATA.records.map(function (record) {
    var spec = specs[record.group];
    var evaluated = D.evaluateRecord(record, spec);
    return { record: record, spec: spec, source: sources[record.source], evaluated: evaluated, verdict: D.verdict(evaluated) };
  });
  var byId = {};
  records.forEach(function (x) { byId[x.record.id] = x; });

  var ICON = {
    ready: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M6.2 11.3 3 8.1l1.1-1.1 2.1 2.1 5.6-5.6L12.9 4.6z"/></svg>',
    hold: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M5 3h2v10H5zm4 0h2v10H9z"/></svg>',
    escalate: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 2 15 14H1zm-.8 4v4h1.6V6zm0 5v1.6h1.6V11z"/></svg>',
    within: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M6.2 11.3 3 8.1l1.1-1.1 2.1 2.1 5.6-5.6L12.9 4.6z"/></svg>',
    borderline: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 1.5a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13zm-.8 3v4.3h1.6V4.5zm0 5.3v1.7h1.6V9.8z"/></svg>',
    out: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m4.1 3 3.9 3.9L11.9 3 13 4.1 9.1 8l3.9 3.9-1.1 1.1L8 9.1 4.1 13 3 11.9 6.9 8 3 4.1z"/></svg>',
    missing: '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 2 15 14H1zm-.8 4v4h1.6V6zm0 5v1.6h1.6V11z"/></svg>'
  };
  var RESULT_LABEL = { within: "Within", borderline: "Borderline", out: "Out of range", missing: "Missing" };

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
      "Record them elsewhere as well.</p></div>";
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
  function statusOf(id) { return D.recordStatus(store.decisions[id]); }
  function chip(kind, label) { return '<span class="chip chip--' + kind + '">' + (ICON[kind] || "") + esc(label) + "</span>"; }

  function parseRoute() {
    var h = (location.hash || "#/queue").slice(1);
    var parts = h.split("?");
    var path = parts[0];
    var query = new URLSearchParams(parts[1] || "");
    var m;
    if ((m = path.match(/^\/record\/([^/]+)\/notice$/))) return { screen: "notice", id: decodeURIComponent(m[1]), query: query };
    if ((m = path.match(/^\/record\/([^/]+)$/))) return { screen: "record", id: decodeURIComponent(m[1]), query: query };
    if (path === "/audit") return { screen: "audit", query: query };
    return { screen: "queue", query: query };
  }

  // ---------------------------------------------------------------------------------------------- queue
  var FILTERS = [["all", "All"], ["needs-review", "Needs review"], ["on-hold", "On hold"], ["approved", "Approved"], ["declined", "Declined"]];

  function visibleRecords() {
    var q = ui.q.trim().toLowerCase();
    return records.filter(function (x) {
      var st = statusOf(x.record.id).id;
      if (ui.filter !== "all" && st !== ui.filter) return false;
      if (!q) return true;
      return [x.record.id, x.record.input, x.spec.group, x.source.name].join(" ").toLowerCase().indexOf(q) >= 0;
    }).sort(function (a, b) {
      var ra = statusOf(a.record.id).id === "needs-review" ? 0 : 1;
      var rb = statusOf(b.record.id).id === "needs-review" ? 0 : 1;
      return ra - rb || b.verdict.tier - a.verdict.tier || a.record.due.localeCompare(b.record.due) || a.record.id.localeCompare(b.record.id);
    });
  }

  function renderQueue(route) {
    var counts = {};
    FILTERS.forEach(function (f) { counts[f[0]] = 0; });
    records.forEach(function (x) { counts.all++; counts[statusOf(x.record.id).id]++; });
    var head = '<div class="page-head"><h1 id="screen-title" tabindex="-1">Record list</h1>' +
      '<p class="lede">Generated records with numeric input fields. Validation compares each input with its configured ' +
      "limits. Actions exercise the technical state machine.</p></div>";
    var ready = ui.loaded && !ui.error;   // no counts or filtering while there is no list to count or filter
    var tools = '<div class="toolbar"><div class="filters" role="group" aria-label="Filter records by status">' +
      FILTERS.map(function (f) {
        return '<button type="button" class="filter" data-filter="' + f[0] + '" aria-pressed="' + (ui.filter === f[0]) + '"' +
               (ready ? "" : " disabled") + ">" + esc(f[1]) + (ready ? ' <span class="count">' + counts[f[0]] + "</span>" : "") + "</button>";
      }).join("") + '</div><div class="search"><label for="search">Search</label>' +
      '<input id="search" type="search" autocomplete="off" placeholder="Record, input, group or source" value="' + esc(ui.q) + '"' +
      (ready ? "" : " disabled") + "></div></div>";
    var body;
    if (!ui.loaded) {
      body = '<div class="state" data-state="loading" aria-busy="true"><p class="state__title">Loading records…</p>' +
             '<div class="skeleton" aria-hidden="true"><span></span><span></span><span></span></div></div>';
    } else if (ui.error) {
      body = '<div class="state state--error" data-state="error" role="alert"><h2 class="state__title">The record list did not load</h2>' +
             "<p>The environment server did not answer (simulated). Nothing you recorded was lost.</p>" +
             '<button type="button" class="btn btn--primary" data-testid="retry">Try again</button></div>';
    } else {
      var rows = visibleRecords();
      if (!rows.length) {
        body = '<div class="state" data-state="empty"><h2 class="state__title">No records match</h2><p>Nothing matches ' +
               (ui.q ? "“" + esc(ui.q) + "”" : "this filter") + (ui.filter !== "all" ? " in " + esc(FILTERS.filter(function (f) { return f[0] === ui.filter; })[0][1]) : "") +
               '.</p><button type="button" class="btn" data-testid="reset-filters">Reset filters</button></div>';
      } else {
        body = '<div class="table-region"><table class="data-table queue-table" data-testid="queue-table">' +
          '<caption class="sr-only">Records with their derived verdict and decision status</caption>' +
          '<thead><tr><th scope="col">Record</th><th scope="col">Group</th><th scope="col">Source</th>' +
          '<th scope="col">Received</th><th scope="col">Verdict</th><th scope="col">Status</th></tr></thead><tbody>' +
          rows.map(function (x) {
            var st = statusOf(x.record.id);
            return '<tr data-record-row="' + esc(x.record.id) + '">' +
              '<td data-label="Record"><span class="cell-stack"><a class="record-link" href="#/record/' + esc(x.record.id) + '" data-record-link="' +
              esc(x.record.id) + '">' + esc(x.record.id) + '</a><span class="sub sub--id">' + esc(x.record.input) + "</span></span></td>" +
              '<td data-label="Group">' + esc(nb(x.spec.group)) + "</td>" +
              '<td data-label="Source">' + esc(x.source.name) + "</td>" +
              '<td data-label="Received"><time datetime="' + esc(x.record.received) + '">' + day(x.record.received) + "</time></td>" +
              '<td data-label="Verdict">' + chip(x.verdict.id, x.verdict.label) + "</td>" +
              '<td data-label="Status">' + chip("status", st.label) + "</td></tr>";
          }).join("") + "</tbody></table></div>" +
          '<p class="table-note">Showing ' + rows.length + " of " + records.length + " records · needs review first, then by verdict " +
          "(escalate, hold, ready) and review due date.</p>";
      }
    }
    return '<section data-screen="queue" aria-labelledby="screen-title">' + head + storageWarning() + tools + body + "</section>";
  }

  // ---------------------------------------------------------------------------------------------- record
  function crumbs(items) {
    return '<nav class="crumbs" aria-label="Breadcrumb"><ol>' + items.map(function (it, i) {
      return "<li>" + (it[1] ? '<a href="' + it[1] + '">' + esc(it[0]) + "</a>" : '<span aria-current="page">' + esc(it[0]) + "</span>") + "</li>";
    }).join("") + "</ol></nav>";
  }

  function notFound(screen, id) {
    return '<section data-screen="' + screen + '" aria-labelledby="screen-title">' + crumbs([["Record list", "#/queue"], [id, null]]) +
      '<div class="state state--error" data-state="error"><h1 id="screen-title" tabindex="-1">Record ' + esc(id) + " was not found</h1>" +
      "<p>It is not in this environment's queue. Check the record number on the delivery note.</p>" +
      '<a class="btn btn--primary" href="#/queue">Back to the record queue</a></div></section>';
  }

  function renderRecord(route) {
    var x = byId[route.id];
    if (!x) return notFound("record", route.id);
    var record = x.record;
    var decided = store.decisions[record.id];
    var v = x.verdict;
    var meta = [["Source", x.source.name], ["Received", day(record.received)], ["Review due", day(record.due)],
                ["Reference", record.ref], ["Input", record.input]];
    var head = crumbs([["Record list", "#/queue"], [record.id, null]]) + '<div class="page-head"><h1 id="screen-title" tabindex="-1">Record ' +
      esc(record.id) + ' <span class="title-sub">' + esc(nb(x.spec.group)) + '</span></h1><dl class="meta">' +
      meta.map(function (m) { return "<div><dt>" + esc(m[0]) + "</dt><dd>" + esc(m[1]) + "</dd></div>"; }).join("") + "</dl></div>";
    var verdictBox = '<div class="verdict verdict--' + v.id + '" data-testid="verdict"><p class="verdict__label">' + ICON[v.id] +
      "<span>Derived verdict: <strong>" + esc(v.label) + "</strong></span></p>" +
      '<p class="verdict__reason">' + esc(v.reason) + ".</p>" +
      '<p class="verdict__rule">Any out-of-range result → Hold. Any missing or unreadable result → Escalate (missing data never lowers the tier). Otherwise → Ready. You make the decision.</p></div>';
    var table = '<section class="comparison" aria-labelledby="cmp-title"><h2 id="cmp-title">Input results against limits</h2>' +
      '<div class="table-region"><table class="data-table comparison-table" data-testid="comparison-table">' +
      '<caption class="sr-only">Each input result compared with its limit</caption>' +
      '<thead><tr><th scope="col">Parameter</th><th scope="col">Limits</th><th scope="col">Input</th>' +
      '<th scope="col">Result</th><th scope="col">How it was derived</th></tr></thead><tbody>' +
      x.evaluated.map(function (r) {
        return "<tr><th scope=\"row\" data-label=\"Parameter\">" + esc(r.name) + '</th><td data-label="Limits">' + esc(r.spec) +
          '</td><td data-label="Input" class="num">' + (r.value === null ? "<em>not readable</em>" : esc(D.fmt(r.value, r.unit))) +
          '</td><td data-label="Result">' + chip(r.status, RESULT_LABEL[r.status]) + '</td><td data-label="How it was derived" class="derivation">' +
          '<span class="cell-stack">' + esc(r.derivation) + (r.note ? '<span class="sub">' + esc(r.note) + "</span>" : "") + "</span></td></tr>";
      }).join("") + "</tbody></table></div></section>";
    var panel;
    if (decided) {
      var st = D.recordStatus(decided);
      panel = '<section class="decision-panel" aria-labelledby="dec-title"><h2 id="dec-title">Verdict and decision</h2>' + verdictBox +
        '<p class="decision-status" data-testid="decision-status" role="status">' + chip("status", st.label) + " " +
        esc(st.label) + " by " + esc(decided.by) + " at " + esc(when(decided.at)) + ".</p>" +
        (decided.rationale ? '<blockquote class="rationale">' + esc(decided.rationale) + "</blockquote>" : "") +
        '<p class="panel-links"><a href="#/audit">See it in the decision log</a>' +
        (decided.decision !== "approve" ? ' · <a data-testid="draft-notice" href="#/record/' + esc(record.id) + '/notice">Draft follow-up note</a>' : "") +
        "</p></section>";
    } else {
      var locked = !D.canApprove(v);
      panel = '<section class="decision-panel" aria-labelledby="dec-title"><h2 id="dec-title">Verdict and decision</h2>' + verdictBox +
        '<form data-testid="decision-form" novalidate><fieldset><legend>Choose a decision</legend>' +
        '<label class="option' + (locked ? " option--locked" : "") + '"><input type="radio" name="decision" id="decision-approve" value="approve"' +
        (locked ? ' disabled aria-describedby="approve-hint"' : "") + "> Approve</label>" +
        (locked ? '<p class="hint" id="approve-hint" data-testid="approve-hint">Approve unlocks when every result is within limits.</p>' : "") +
        '<label class="option"><input type="radio" name="decision" id="decision-hold" value="hold"> Hold</label>' +
        '<label class="option"><input type="radio" name="decision" id="decision-decline" value="decline"> Decline</label>' +
        '<p class="field-error" id="decision-error" data-testid="decision-error"></p></fieldset>' +
        '<label for="rationale" class="field-label">Rationale <span class="hint">required for hold and decline — at least ' + D.MIN_RATIONALE + " characters</span></label>" +
        '<textarea id="rationale" rows="4" aria-describedby="rationale-count rationale-error"></textarea>' +
        '<p class="hint" id="rationale-count">0 characters</p>' +
        '<p class="field-error" id="rationale-error" data-testid="rationale-error"></p>' +
        '<button type="submit" class="btn btn--primary" data-testid="record-decision">Record decision</button></form>' +
        '<p class="decision-status" data-testid="decision-status" role="status"></p></section>';
    }
    return '<section data-screen="record" aria-labelledby="screen-title">' + head +
      '<div class="record-layout">' + table + '<div class="decision-col">' + storageWarning() + panel + "</div></div></section>";
  }

  // ---------------------------------------------------------------------------------------------- notice
  function renderNotice(route) {
    var x = byId[route.id];
    if (!x) return notFound("notice", route.id);
    var head = crumbs([["Record list", "#/queue"], [x.record.id, "#/record/" + encodeURIComponent(x.record.id)], ["Follow-up note", null]]);
    if (D.canApprove(x.verdict)) {
      return '<section data-screen="notice" aria-labelledby="screen-title">' + head +
        '<div class="state" data-state="not-needed"><h1 id="screen-title" tabindex="-1">No notice needed for ' + esc(x.record.id) + "</h1>" +
        "<p>Every result on input " + esc(x.record.input) + " is within limits.</p>" +
        '<a class="btn" href="#/record/' + esc(x.record.id) + '">Back to the record</a></div></section>';
    }
    var decided = store.decisions[x.record.id];
    var draft = D.noticeDraft(x.record, x.spec.group, x.source, x.evaluated, decided);
    var saved = store.notices[x.record.id];
    var decLine = '<p class="notice-decision" data-testid="notice-decision">' + (decided
      ? chip("status", D.recordStatus(decided).label) + " " + esc(D.recordStatus(decided).label) + " by " + esc(decided.by) + " at " + esc(when(decided.at)) + "."
      : "No decision recorded for this record yet.") + "</p>";
    return '<section data-screen="notice" aria-labelledby="screen-title">' + head +
      '<div class="page-head"><h1 id="screen-title" tabindex="-1">Follow-up note draft · ' + esc(x.record.id) + "</h1>" + decLine + "</div>" + storageWarning() +
      '<p class="banner" role="note"><strong>Draft only.</strong> Sending happens outside this prototype; nothing leaves this page.</p>' +
      '<div class="notice-layout"><section aria-labelledby="issues-title"><h2 id="issues-title">What needs follow-up</h2>' +
      '<ul class="issues" data-testid="notice-issues">' + draft.issues.map(function (r) {
        return "<li>" + chip(r.status, RESULT_LABEL[r.status]) + " <strong>" + esc(r.name) + "</strong>: " +
          (r.value === null ? "no readable value" : esc(D.fmt(r.value, r.unit))) + " (limits " + esc(r.spec) + ")</li>";
      }).join("") + "</ul></section>" +
      '<section aria-labelledby="text-title"><h2 id="text-title">Notice text</h2><textarea id="notice-body" rows="12" aria-labelledby="text-title">' +
      esc(saved ? saved.text : draft.text) + "</textarea>" +
      '<div class="actions"><button type="button" class="btn btn--primary" data-testid="save-draft">Save draft</button>' +
      '<a class="btn" href="#/record/' + esc(x.record.id) + '">Back to the record</a></div>' +
      '<p class="decision-status" data-testid="notice-status" role="status">' +
      (saved ? "Draft saved — not sent (" + esc(when(saved.at)) + ")." : "") + "</p></section></div></section>";
  }

  // ---------------------------------------------------------------------------------------------- audit
  var DECISION_LABEL = { approve: "Approved", hold: "On hold", decline: "Declined" };

  function renderAudit() {
    var head = '<div class="page-head"><h1 id="screen-title" tabindex="-1">Decision log</h1><p class="lede">Every decision, who made it, ' +
      "when, and the derived verdict at that moment. Newest first.</p></div>";
    var rows = store.log.slice().reverse().concat(HISTORY);
    if (!rows.length) {
      return '<section data-screen="audit" aria-labelledby="screen-title">' + head + storageWarning() +
        '<div class="state" data-state="empty"><h2 class="state__title">No decisions recorded yet</h2>' +
        "<p>Decisions you record on a record appear here with their rationale.</p>" +
        '<a class="btn btn--primary" href="#/queue">Go to the record queue</a></div></section>';
    }
    return '<section data-screen="audit" aria-labelledby="screen-title">' + head + storageWarning() +
      '<div class="table-region"><table class="data-table audit-table" data-testid="audit-table">' +
      '<caption class="sr-only">Recorded decisions, newest first</caption><thead><tr><th scope="col">Time</th>' +
      '<th scope="col">Record</th><th scope="col">Decision</th><th scope="col">Verdict at decision</th>' +
      '<th scope="col">Rationale</th><th scope="col">Reviewer</th></tr></thead><tbody>' +
      rows.map(function (e) {
        return '<tr><td data-label="Time"><time datetime="' + esc(e.at) + '">' + esc(when(e.at)) + "</time></td>" +
          '<td data-label="Record">' + (byId[e.record] ? '<a class="record-link" href="#/record/' + esc(e.record) + '">' + esc(e.record) + "</a>"
            : '<span class="cell-stack"><span class="record-id">' + esc(e.record) + '</span><span class="sub">Previous test run</span></span>') + "</td>" +
          '<td data-label="Decision">' + chip("status", DECISION_LABEL[e.decision]) + "</td>" +
          '<td data-label="Verdict at decision">' + chip(e.verdict, e.verdictLabel) + "</td>" +
          '<td data-label="Rationale">' + (e.rationale ? esc(e.rationale) : "<em>none given</em>") + "</td>" +
          '<td data-label="Reviewer">' + esc(e.by) + "</td></tr>";
      }).join("") + "</tbody></table></div>" +
      (HISTORY.length ? '<p class="table-note">' + store.log.length + " decision" + (store.log.length === 1 ? "" : "s") +
        " this session · " + HISTORY.length + " from the previous test run (synthetic).</p>" : "") + "</section>";
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
      if (ui.error) announce("The record list did not load. Use Try again.");
    }, 150);
  }

  function render() {
    var route = parseRoute();
    if (location.hash !== lastHash) {
      lastHash = location.hash;
      if (route.screen === "queue" && route.query.get("q") !== null) ui.q = route.query.get("q");
    }
    var html = route.screen === "record" ? renderRecord(route) : route.screen === "notice" ? renderNotice(route)
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
    document.title = (title ? title.textContent.replace(/\s+/g, " ").trim() + " — " : "") + "Workflow test harness (synthetic)";
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
    var entry = { record: x.record.id, decision: decision, rationale: rationale.trim(), verdict: x.verdict.id,
                  verdictLabel: x.verdict.label, by: REVIEWER, at: new Date().toISOString() };
    store.decisions[x.record.id] = entry;
    store.log.push(entry);
    saveStore();
    render();
    announce("Decision recorded: record " + x.record.id + " " + DECISION_LABEL[decision].toLowerCase() + ".");
  }

  app.addEventListener("click", function (ev) {
    var t = ev.target.closest("button, a");
    if (!t) return;
    if (t.hasAttribute("data-filter")) {
      ui.filter = t.getAttribute("data-filter");
      render();
      var again = app.querySelector('[data-filter="' + ui.filter + '"]');
      if (again && ev.detail === 0) again.focus();
      announce(app.querySelector(".table-note") ? app.querySelector(".table-note").textContent : "No records match.");
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
      announce("Filters reset. Showing all " + records.length + " records.");
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

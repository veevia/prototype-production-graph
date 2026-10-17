/* Lot Release Workbench — domain logic (fictional example for the pdg workflow).
 *
 * Pure functions, no DOM: the same file runs in the browser (window.LotDomain) and under `node --test`.
 * Rules implemented here come from the example's requirements (controls/product.md):
 *   R-02 every CoA result is compared with its specification limit, and the derivation is shown
 *   R-03 a lot can be released only when every result is within specification
 *   R-04 hold and reject need a rationale of at least 20 characters
 *   missing or unreadable data escalates the verdict a tier; it never lowers one
 */
(function (root) {
  "use strict";

  var BORDERLINE_FRACTION = 0.1; // within 10 % of a limit is flagged borderline (still within)
  var MIN_RATIONALE = 20;
  var TIER = { ready: 0, hold: 1, escalate: 2 };
  var NB = "\u00a0"; // a value never wraps away from its unit or comparator

  function fmt(x, unit) {
    if (x === null || x === undefined || x === Infinity || x === -Infinity) return "—";
    var s = Math.abs(x) >= 100 ? String(Math.round(x)) : String(Number(x.toFixed(3)));
    return unit ? s + NB + unit : s;
  }

  function specText(p) {
    var hasMin = typeof p.min === "number";
    var hasMax = typeof p.max === "number";
    if (hasMin && hasMax) return fmt(p.min) + "\u2060–\u2060" + fmt(p.max) + (p.unit ? NB + p.unit : "");
    if (hasMax) return "≤" + NB + fmt(p.max, p.unit);
    if (hasMin) return "≥" + NB + fmt(p.min, p.unit);
    return "reported only";
  }

  /** Compare one CoA value with its specification. Returns {status, derivation}. */
  function evaluateResult(p, value) {
    if (value === null || value === undefined || typeof value !== "number" || isNaN(value)) {
      return { status: "missing", derivation: "No readable value on the certificate → escalate (missing data never lowers the tier)" };
    }
    var lo = typeof p.min === "number" ? p.min : -Infinity;
    var hi = typeof p.max === "number" ? p.max : Infinity;
    if (value < lo) return { status: "out", derivation: fmt(value) + " < " + fmt(lo) + " minimum → out of specification" };
    if (value > hi) return { status: "out", derivation: fmt(value) + " > " + fmt(hi) + " maximum → out of specification" };
    // Borderline margin: explicit in the spec, else 10 % of a two-sided range or of a maximum. A minimum-only limit
    // (for example purity ≥ 99.9 %) is never borderline unless the spec declares a margin.
    var margin = typeof p.borderline_margin === "number" ? p.borderline_margin
      : isFinite(lo) && isFinite(hi) ? BORDERLINE_FRACTION * (hi - lo)
      : isFinite(hi) ? BORDERLINE_FRACTION * Math.abs(hi) : 0;
    var near = margin > 0 && ((isFinite(hi) && hi - value <= margin) || (isFinite(lo) && value - lo <= margin));
    var range = isFinite(lo) && isFinite(hi) ? fmt(lo) + " ≤ " + fmt(value) + " ≤ " + fmt(hi)
      : isFinite(hi) ? fmt(value) + " ≤ " + fmt(hi) + " maximum" : fmt(value) + " ≥ " + fmt(lo) + " minimum";
    if (near) return { status: "borderline", derivation: range + ", within " + fmt(margin) + " of a limit → within, flagged borderline" };
    return { status: "within", derivation: range + " → within specification" };
  }

  /** Evaluate every parameter of a lot against its material specification. */
  function evaluateLot(lot, spec) {
    return spec.parameters.map(function (p) {
      var v = Object.prototype.hasOwnProperty.call(lot.results, p.id) ? lot.results[p.id] : null;
      var r = evaluateResult(p, v);
      return { id: p.id, name: p.name, unit: p.unit, spec: specText(p), value: v,
               status: r.status, derivation: r.derivation, note: (lot.notes || {})[p.id] || "" };
    });
  }

  /** The derived verdict: the highest tier any result demands. */
  function verdict(evaluated) {
    var missing = evaluated.filter(function (r) { return r.status === "missing"; });
    var out = evaluated.filter(function (r) { return r.status === "out"; });
    var border = evaluated.filter(function (r) { return r.status === "borderline"; });
    if (missing.length) {
      return { id: "escalate", label: "Escalate to QA lead", tier: TIER.escalate,
               reason: missing.length + (missing.length === 1 ? " result is" : " results are") + " missing or unreadable" +
                       (out.length ? "; " + out.length + " out of specification" : "") };
    }
    if (out.length) {
      return { id: "hold", label: "Hold", tier: TIER.hold,
               reason: out.length + (out.length === 1 ? " result is" : " results are") + " out of specification: " +
                       out.map(function (r) { return r.name; }).join(", ") };
    }
    return { id: "ready", label: "Ready to release", tier: TIER.ready,
             reason: "All " + evaluated.length + " results within specification" +
                     (border.length ? " (" + border.length + " borderline: " + border.map(function (r) { return r.name; }).join(", ") + ")" : "") };
  }

  function canRelease(v) { return v.id === "ready"; }

  /** Validate a reviewer's decision. Returns a list of {field, message}; empty means valid. */
  function validateDecision(decision, rationale, v) {
    var errors = [];
    var text = (rationale || "").trim();
    if (["release", "hold", "reject"].indexOf(decision) < 0) {
      errors.push({ field: "decision", message: "Choose release, hold or reject." });
      return errors;
    }
    if (decision === "release" && !canRelease(v)) {
      errors.push({ field: "decision", message: "Release unlocks when every result is within specification." });
    }
    if ((decision === "hold" || decision === "reject") && text.length < MIN_RATIONALE) {
      errors.push({ field: "rationale", message: "Write a rationale of at least 20 characters (" + text.length + " so far)." });
    }
    return errors;
  }

  /** Draft (never send) a supplier notice for a lot that is held or escalated. */
  var NOTICE_CLOSING = {
    hold: "Please send a corrected certificate or a retest result. The lot stays on hold until then.",
    reject: "We have rejected this lot. Please arrange its collection, and send a corrective action for future deliveries.",
    none: "Please send a corrected certificate or a retest result. No release decision has been recorded yet."
  };

  function noticeDraft(lot, material, supplier, evaluated, decision) {
    var issues = evaluated.filter(function (r) { return r.status === "out" || r.status === "missing"; });
    var lines = [
      "To: " + supplier.contact + " (" + supplier.name + ")",
      "Subject: Lot " + lot.id + " — certificate " + lot.coa + " needs attention",
      "",
      "We reviewed certificate " + lot.coa + " for lot " + lot.id + " (" + material + ", " + lot.po + ").",
      issues.length ? "These results need your action:" : "No results need action."
    ];
    issues.forEach(function (r) {
      lines.push("- " + r.name + ": " + (r.status === "missing" ? "no readable value" : fmt(r.value, r.unit)) +
                 " (specification " + r.spec + ")");
    });
    lines.push("", NOTICE_CLOSING[decision && NOTICE_CLOSING[decision.decision] ? decision.decision : "none"]);
    return { issues: issues, text: lines.join("\n") };
  }

  function lotStatus(decision) {
    if (!decision) return { id: "needs-review", label: "Needs review" };
    return { release: { id: "released", label: "Released" }, hold: { id: "on-hold", label: "On hold" },
             reject: { id: "rejected", label: "Rejected" } }[decision.decision];
  }

  var api = { evaluateResult: evaluateResult, evaluateLot: evaluateLot, verdict: verdict, canRelease: canRelease,
              validateDecision: validateDecision, noticeDraft: noticeDraft, lotStatus: lotStatus, specText: specText,
              fmt: fmt, MIN_RATIONALE: MIN_RATIONALE, BORDERLINE_FRACTION: BORDERLINE_FRACTION };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.LotDomain = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

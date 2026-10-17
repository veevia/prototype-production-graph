// Unit tests for the Lot Release Workbench domain logic: node --test tests/domain.test.js
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const D = require("../src/domain.js");

const BRIX = { id: "brix", name: "Brix", unit: "°Bx", min: 66.5, max: 67.5 };
const LEAD = { id: "lead", name: "Lead", unit: "mg/kg", max: 0.5 };
const PURITY = { id: "purity", name: "Purity", unit: "% v/v", min: 99.9 };

test("a value inside the limits is within, with its derivation", () => {
  const r = D.evaluateResult(BRIX, 67.0);
  assert.equal(r.status, "within");
  assert.match(r.derivation, /66\.5 ≤ 67 ≤ 67\.5/);
});

test("above the maximum and below the minimum are out of specification", () => {
  assert.equal(D.evaluateResult(BRIX, 67.9).status, "out");
  assert.match(D.evaluateResult(BRIX, 67.9).derivation, /> 67\.5 maximum/);
  assert.equal(D.evaluateResult(BRIX, 66.0).status, "out");
  assert.equal(D.evaluateResult(PURITY, 99.8).status, "out");
});

test("close to a limit is borderline but still within", () => {
  assert.equal(D.evaluateResult(BRIX, 67.45).status, "borderline");
  assert.equal(D.evaluateResult(LEAD, 0.48).status, "borderline");
  assert.equal(D.evaluateResult(LEAD, 0.2).status, "within");
  assert.equal(D.evaluateResult(PURITY, 99.95).status, "within", "a minimum-only limit needs an explicit margin");
  assert.equal(D.evaluateResult({ ...PURITY, borderline_margin: 0.02 }, 99.91).status, "borderline");
});

test("a missing or unreadable value is missing", () => {
  assert.equal(D.evaluateResult(BRIX, null).status, "missing");
  assert.equal(D.evaluateResult(BRIX, undefined).status, "missing");
  assert.equal(D.evaluateResult(BRIX, NaN).status, "missing");
});

test("the verdict takes the highest tier: missing escalates and never lowers", () => {
  const spec = { parameters: [BRIX, LEAD] };
  assert.equal(D.verdict(D.evaluateLot({ results: { brix: 67, lead: 0.1 } }, spec)).id, "ready");
  assert.equal(D.verdict(D.evaluateLot({ results: { brix: 68, lead: 0.1 } }, spec)).id, "hold");
  const both = D.verdict(D.evaluateLot({ results: { brix: 68, lead: null } }, spec));
  assert.equal(both.id, "escalate");
  assert.match(both.reason, /missing or unreadable; 1 out of specification/);
  assert.equal(D.verdict(D.evaluateLot({ results: { brix: 67 } }, spec)).id, "escalate");
});

test("release is allowed only when the verdict is ready", () => {
  const ready = { id: "ready" };
  const hold = { id: "hold" };
  assert.deepEqual(D.validateDecision("release", "", ready), []);
  assert.equal(D.validateDecision("release", "a long enough rationale here", hold)[0].field, "decision");
});

test("hold and reject need a rationale of at least 20 characters", () => {
  const hold = { id: "hold" };
  const errs = D.validateDecision("hold", "Too short", hold);
  assert.equal(errs.length, 1);
  assert.match(errs[0].message, /at least 20 characters \(9 so far\)/);
  assert.deepEqual(D.validateDecision("reject", "Brix above the 67.5 maximum on the certificate", hold), []);
  assert.equal(D.validateDecision("", "", hold)[0].field, "decision");
});

test("a notice draft lists what needs action and never claims to be sent", () => {
  const spec = { parameters: [BRIX, LEAD] };
  const lot = { id: "L-1", coa: "CoA-1", po: "PO-1", results: { brix: 68, lead: null } };
  const d = D.noticeDraft(lot, "Liquid sucrose", { name: "Northwind Sweeteners", contact: "q@x.example" }, D.evaluateLot(lot, spec));
  assert.equal(d.issues.length, 2);
  assert.match(d.text, /Brix: 68\u00a0°Bx \(specification 66\.5\u2060–\u206067\.5\u00a0°Bx\)/);
  assert.match(d.text, /Lead: no readable value/);
  assert.match(d.text, /No release decision has been recorded yet/);
  assert.doesNotMatch(d.text, /\bsent\b/i);
  assert.doesNotMatch(d.text, /PO PO/);
});

test("the notice's closing line follows the recorded decision", () => {
  const spec = { parameters: [BRIX] };
  const lot = { id: "L-2", coa: "CoA-2", po: "PO-2", results: { brix: 68 } };
  const draft = (decision) => D.noticeDraft(lot, "Liquid sucrose", { name: "N", contact: "q@x.example" }, D.evaluateLot(lot, spec), decision).text;
  assert.match(draft({ decision: "hold" }), /stays on hold until then/);
  assert.match(draft({ decision: "reject" }), /We have rejected this lot/);
  assert.doesNotMatch(draft({ decision: "reject" }), /stays on hold/);
});

test("specification text and lot status labels", () => {
  assert.equal(D.specText(BRIX), "66.5\u2060–\u206067.5\u00a0°Bx");
  assert.equal(D.specText(LEAD), "≤\u00a00.5\u00a0mg/kg");
  assert.equal(D.specText(PURITY), "≥\u00a099.9\u00a0% v/v");
  assert.equal(D.lotStatus(undefined).label, "Needs review");
  assert.equal(D.lotStatus({ decision: "hold" }).label, "On hold");
});

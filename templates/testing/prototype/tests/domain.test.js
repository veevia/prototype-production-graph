"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const rules = require("../src/domain.js");
const field = { id: "field_a", name: "Field A", unit: "", min: 0, max: 10 };

test("numeric boundary checks retain their derivation", () => {
  assert.equal(rules.evaluateResult(field, 5).status, "within");
  assert.equal(rules.evaluateResult(field, 12).status, "out");
  assert.equal(rules.evaluateResult(field, -1).status, "out");
  assert.equal(rules.evaluateResult(field, 9.5).status, "borderline");
  assert.equal(rules.evaluateResult(field, null).status, "missing");
  assert.equal(rules.evaluateResult(field, NaN).status, "missing");
});

test("missing inputs do not produce a lower validation tier", () => {
  const spec = { parameters: [field] };
  assert.equal(rules.verdict(rules.evaluateRecord({ results: { field_a: 5 } }, spec)).id, "ready");
  assert.equal(rules.verdict(rules.evaluateRecord({ results: { field_a: 12 } }, spec)).id, "hold");
  assert.equal(rules.verdict(rules.evaluateRecord({ results: {} }, spec)).id, "escalate");
});

test("state transitions enforce their input conditions", () => {
  assert.deepEqual(rules.validateDecision("approve", "", { id: "ready" }), []);
  assert.equal(rules.validateDecision("approve", "", { id: "hold" })[0].field, "decision");
  assert.equal(rules.validateDecision("hold", "short", { id: "hold" })[0].field, "rationale");
  assert.deepEqual(rules.validateDecision("hold", "A sufficiently long synthetic test reason.", { id: "hold" }), []);
});

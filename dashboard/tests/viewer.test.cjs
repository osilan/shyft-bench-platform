const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const {
  resolveFigures,
  selectorOptions,
} = require("../../.dashboard-test-build/viewer.js");

const fixture = path.resolve(__dirname, "../../tests/fixtures/dashboard-export");
const figures = JSON.parse(fs.readFileSync(path.join(fixture, "figure-index.json"), "utf8")).figures;
const canonical = JSON.parse(fs.readFileSync(path.resolve(fixture, "../../../pipeline/canon.json"), "utf8"));
const selection = {
  forcing: "seNorge",
  direction: "forward",
  pcorr: false,
  optimizer: "bobyqa",
};

test("fixture IDs are the Lean-exported first-slice declarations", () => {
  assert.deepEqual(figures.map(({ id }) => id), canonical.firstSlice);
});

test("selectors cascade through only forcing values declared in the fixture index", () => {
  assert.deepEqual(selectorOptions(figures, "forcing", {}), ["seNorge"]);
  assert.deepEqual(selectorOptions(figures, "direction", { forcing: "seNorge" }), ["forward"]);
  assert.deepEqual(selectorOptions(figures, "pcorr", {
    forcing: "seNorge",
    direction: "forward",
  }), [false, true]);
  assert.deepEqual(selectorOptions(figures, "optimizer", {
    forcing: "seNorge",
    direction: "forward",
    pcorr: true,
  }), ["bobyqa"]);
  assert.equal(selectorOptions(figures, "forcing", {}).includes("AIFS"), false);
});

test("each selected indexed figure pairs its SVG with its own CSV table", () => {
  for (const figure of figures) {
    const selected = resolveFigures(figures, {
      forcing: figure.forcing,
      direction: figure.direction,
      pcorr: figure.pcorr,
      optimizer: figure.optimizer,
    });
    assert.deepEqual(selected.map(({ id }) => id), [figure.id]);
    assert.match(fs.readFileSync(path.join(fixture, figure.svg), "utf8"), /<svg/);
    const table = fs.readFileSync(path.join(fixture, figure.csv), "utf8");
    assert.match(table, /metric,value/);
    assert.match(table, new RegExp(figure.pcorr ? "synthetic on" : "synthetic off"));
  }
});

test("an undeclared figure cannot be resolved from the index", () => {
  assert.deepEqual(resolveFigures(figures, { ...selection, forcing: "AIFS" }), []);
});

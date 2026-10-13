const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const viewer = require("../../.dashboard-test-build/viewer.js");

const fixture = path.resolve(__dirname, "../../tests/fixtures/dashboard-export");
const indexed = JSON.parse(fs.readFileSync(path.join(fixture, "figure-index.json"), "utf8")).figures;
const canonical = JSON.parse(fs.readFileSync(path.resolve(fixture, "../../../pipeline/canon.json"), "utf8"));

function fig(id, fields = {}) {
  return {
    id, view: id.split("-")[0], forcing: "seNorge", direction: "forward", pcorr: null,
    optimizer: "bobyqa", svg: `figures/${id}.svg`, csv: `tables/${id}.csv`, ...fields,
  };
}

// Two published pages, one planned; one declared figure is not built; one built figure is on no page.
const synthetic = {
  canon: {
    pages: [
      { key: "models", title: "Models", status: "published", selectors: ["pcorr"],
        figures: ["score-off", "score-on", "compare", "missing"] },
      { key: "goals", title: "Goals", status: "published", selectors: ["model", "pcorr"],
        figures: ["gen-a-off", "gen-a-on", "gen-b-off", "gen-b-on"] },
      { key: "later", title: "Later", status: "planned", selectors: [], figures: ["later"] },
    ],
    pageFigures: [
      { id: "gen-a-off", model: "ptstk", goal: null }, { id: "gen-a-on", model: "ptstk", goal: null },
      { id: "gen-b-off", model: "rpmstk", goal: null }, { id: "gen-b-on", model: "rpmstk", goal: null },
    ],
  },
  index: [
    fig("score-off", { pcorr: false }), fig("score-on", { pcorr: true }), fig("compare"),
    fig("gen-a-off", { pcorr: false }), fig("gen-a-on", { pcorr: true }),
    fig("gen-b-off", { pcorr: false }), fig("gen-b-on", { pcorr: true }),
    fig("later"), fig("stray", { pcorr: true }),
  ],
};

test("fixture IDs are the Lean-exported first-slice declarations", () => {
  assert.deepEqual(indexed.map(({ id }) => id), canonical.firstSlice);
});

test("with the real canon, only pages with built figures appear, in Lean's order", () => {
  const pages = viewer.buildPages(canonical, indexed);
  assert.deepEqual(pages.map(({ key }) => key), ["models-pcorr"]);
  assert.deepEqual(pages[0].figures.map(({ id }) => id), canonical.firstSlice);
  assert.deepEqual(pages[0].selectors, ["pcorr"]);
});

test("menu: published pages only, missing figures skipped, unpaged figures under Other", () => {
  const pages = viewer.buildPages(synthetic.canon, synthetic.index);
  assert.deepEqual(pages.map(({ key }) => key), ["models", "goals", viewer.OTHER_PAGE_KEY]);
  assert.deepEqual(pages[0].figures.map(({ id }) => id), ["score-off", "score-on", "compare"]);
  assert.deepEqual(pages[2].figures.map(({ id }) => id), ["stray"]);
  assert.equal(pages[1].figures[2].model, "rpmstk");
});

test("without pages in the canon, every figure is on the Other page", () => {
  const pages = viewer.buildPages({}, indexed);
  assert.deepEqual(pages.map(({ key }) => key), [viewer.OTHER_PAGE_KEY]);
  assert.deepEqual(pages[0].selectors, ["pcorr"]);
});

test("selectors are the page's own, with values present on that page", () => {
  const [models, goals] = viewer.buildPages(synthetic.canon, synthetic.index);
  assert.deepEqual(viewer.selectorsFor(models), ["forcing", "pcorr"]);
  assert.deepEqual(viewer.selectorOptions(models, "pcorr", { forcing: "seNorge" }), [false, true]);
  assert.deepEqual(viewer.selectorsFor(goals), ["forcing", "model", "pcorr"]);
  assert.deepEqual(viewer.selectorOptions(goals, "model", { forcing: "seNorge" }), ["ptstk", "rpmstk"]);
});

test("a figure that does not vary on a selector is shown for every value of it", () => {
  const [models] = viewer.buildPages(synthetic.canon, synthetic.index);
  const on = viewer.settleSelection(models, { pcorr: true });
  assert.deepEqual(viewer.figuresFor(models, on).map(({ id }) => id), ["score-on", "compare"]);
  const off = viewer.settleSelection(models, { pcorr: false });
  assert.deepEqual(viewer.figuresFor(models, off).map(({ id }) => id), ["score-off", "compare"]);
});

test("model and pcorr together pick exactly one figure", () => {
  const [, goals] = viewer.buildPages(synthetic.canon, synthetic.index);
  const selection = viewer.settleSelection(goals, { model: "rpmstk", pcorr: false });
  assert.deepEqual(viewer.figuresFor(goals, selection).map(({ id }) => id), ["gen-b-off"]);
});

test("an unknown wanted value falls back to the first option", () => {
  const [, goals] = viewer.buildPages(synthetic.canon, synthetic.index);
  const selection = viewer.settleSelection(goals, { forcing: "aifs", model: "lstm", pcorr: true });
  assert.deepEqual(selection, { forcing: "seNorge", model: "ptstk", pcorr: true });
});

test("table cells: numbers to three significant digits, text and integers unchanged", () => {
  assert.equal(viewer.formatCell("0.633452"), "0.633");
  assert.equal(viewer.formatCell("-0.003482"), "-0.00348");
  assert.equal(viewer.formatCell("17.84321"), "17.8");
  assert.equal(viewer.formatCell("1234.567"), "1230");
  assert.equal(viewer.formatCell("98"), "98");
  assert.equal(viewer.formatCell("1.5e-07"), "1.5e-7");
  assert.equal(viewer.formatCell("ptstk"), "ptstk");
  assert.equal(viewer.formatCell(""), "");
});

test("identifier columns are never rounded: station 109.29 stays 109.29", () => {
  const rows = [["station", "model", "kge_gupta_2009", "n"], ["109.29", "ptstk", "0.633452", "98"]];
  assert.deepEqual(viewer.formatTable(rows), [rows[0], ["109.29", "ptstk", "0.633", "98"]]);
  assert.equal(viewer.isIdentifierColumn("experiment_id"), true);
  assert.equal(viewer.isIdentifierColumn("median_kge_gupta_2009"), false);
});

test("URL state round-trips page and selection", () => {
  const state = { page: "goals", selection: { forcing: "seNorge", model: "rpmstk", pcorr: false } };
  const query = viewer.stateToQuery(state);
  assert.equal(query, "?page=goals&forcing=seNorge&pcorr=false&model=rpmstk");
  assert.deepEqual(viewer.queryToState(query), state);
  assert.deepEqual(viewer.queryToState(""), { selection: {} });
});

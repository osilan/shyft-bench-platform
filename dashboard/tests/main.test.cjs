const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

class Element {
  constructor(tag = "div") {
    this.tagName = tag;
    this.children = [];
    this.listeners = {};
    this.attributes = {};
    this.value = "";
    this.textContent = "";
    this.open = false;
  }

  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(event, listener) { (this.listeners[event] ??= []).push(listener); }
  dispatch(event) { (this.listeners[event] ?? []).forEach((listener) => listener({ preventDefault() {} })); }
  find(tag) {
    if (this.tagName === tag) return this;
    for (const child of this.children) {
      const found = child.find?.(tag);
      if (found) return found;
    }
    return undefined;
  }
}

test("production build packages the pipeline export, not synthetic fixtures", () => {
  const pkg = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../package.json"), "utf8"));
  assert.match(pkg.scripts.build, /cp -R dist-data\/\. dist\//);
  assert.doesNotMatch(pkg.scripts.build, /tests\/fixtures/);
});

test("pages, selectors, full-width figures and a folded table that loads on opening", async (t) => {
  const saved = { document: global.document, fetch: global.fetch, history: global.history, location: global.location };
  const figure = (id, pcorr) => ({
    id, view: "scoreboard", forcing: "seNorge", direction: "forward", pcorr, optimizer: "bobyqa",
    svg: `figures/${id}.svg`, csv: `tables/${id}.csv`,
  });
  const index = { figures: [figure("off", false), figure("on", true)] };
  const canon = {
    pages: [
      { key: "models-pcorr", title: "Models and precipitation correction", status: "published",
        selectors: ["pcorr"], figures: ["off", "on"] },
      { key: "robustness", title: "Robustness", status: "planned", selectors: [], figures: [] },
    ],
    pageFigures: [],
  };
  const elements = Object.fromEntries(["pages", "selectors", "figures", "error"].map((id) => [id, new Element()]));
  const fetched = [];
  let query = "";
  global.document = {
    baseURI: "https://example.test/",
    querySelector: (selector) => elements[selector.slice(1)],
    createElement: (tag) => new Element(tag),
  };
  global.location = { search: "?page=models-pcorr&pcorr=true" };
  global.history = { replaceState: (_s, _t, url) => { query = url; } };
  global.fetch = (url) => {
    const name = url.toString().replace("https://example.test/", "");
    fetched.push(name);
    if (name === "figure-index.json") return Promise.resolve({ ok: true, json: async () => index });
    if (name === "canon.json") return Promise.resolve({ ok: true, json: async () => canon });
    return Promise.resolve({ ok: true, text: async () => "model,median_kge_gupta_2009\nptstk,0.633452\n" });
  };
  const mainPath = path.resolve(__dirname, "../../.dashboard-test-build/main.js");
  delete require.cache[mainPath];
  require(mainPath);
  t.after(() => {
    delete require.cache[mainPath];
    Object.assign(global, saved);
  });
  await new Promise(setImmediate);

  assert.deepEqual(elements.pages.children.map((link) => link.textContent), ["Models and precipitation correction"]);
  assert.equal(elements.pages.children[0].attributes["aria-current"], "page");
  assert.equal(elements.selectors.children.length, 1, "only pcorr varies on this page");
  assert.equal(elements.selectors.children[0].find("select").value, "true", "selection restored from the URL");
  assert.equal(query, "?page=models-pcorr&forcing=seNorge&pcorr=true");

  assert.equal(elements.figures.children.length, 1);
  const block = elements.figures.children[0];
  assert.equal(block.find("img").src, "https://example.test/figures/on.svg");
  const details = block.find("details");
  assert.equal(details.open, false, "the table is folded");
  assert.equal(block.find("a").href, "https://example.test/tables/on.csv");
  assert.equal("download" in block.find("a").attributes, true);
  assert.equal(fetched.includes("tables/on.csv"), false, "the CSV is not loaded before opening");

  details.open = true;
  details.dispatch("toggle");
  await new Promise(setImmediate);
  const table = block.find("table");
  assert.deepEqual(table.children[1].children.map((cell) => cell.textContent), ["ptstk", "0.633"]);

  elements.selectors.children[0].find("select").value = "false";
  elements.selectors.children[0].find("select").dispatch("change");
  assert.equal(elements.figures.children[0].find("img").src, "https://example.test/figures/off.svg");
  assert.equal(query, "?page=models-pcorr&forcing=seNorge&pcorr=false");
});

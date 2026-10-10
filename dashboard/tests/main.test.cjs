const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

class Element {
  constructor() {
    this.children = [];
    this.listeners = {};
    this.value = "";
    this.hidden = false;
    this.textContent = "";
    this.src = "";
  }

  replaceChildren(...children) {
    this.children = children;
  }

  append(child) {
    this.children.push(child);
  }

  addEventListener(event, listener, options) {
    (this.listeners[event] ??= []).push({ listener, once: options?.once ?? false });
  }

  dispatch(event) {
    const listeners = this.listeners[event] ?? [];
    this.listeners[event] = listeners.filter(({ once }) => !once);
    listeners.forEach(({ listener }) => listener({ type: event, target: this }));
  }

  removeAttribute(name) {
    if (name === "src") this.src = "";
  }
}

test("production build packages the pipeline export, not synthetic fixtures", () => {
  const pkg = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../package.json"), "utf8"));
  assert.match(pkg.scripts.build, /cp -R dist-data\/\. dist\//);
  assert.doesNotMatch(pkg.scripts.build, /tests\/fixtures/);
});

test("plot and table stay hidden until the selected figure CSV is loaded", async (t) => {
  const originalDocument = global.document;
  const originalFetch = global.fetch;
  const elements = Object.fromEntries(
    ["forcing", "direction", "pcorr", "optimizer", "figure", "plot", "data", "error"]
      .map((id) => [id, new Element()]),
  );
  const figures = ["first", "second"].map((id) => ({
    id,
    view: id,
    forcing: "seNorge",
    direction: "forward",
    pcorr: false,
    optimizer: "bobyqa",
    svg: `figures/${id}.svg`,
    csv: `tables/${id}.csv`,
  }));
  const csvResponses = [];
  global.document = {
    baseURI: "https://example.test/",
    querySelector: (selector) => elements[selector.slice(1)],
    createElement: () => new Element(),
  };
  global.fetch = (url) => {
    if (url.toString() === "https://example.test/figure-index.json") {
      return Promise.resolve({ ok: true, json: async () => ({ figures }) });
    }
    return new Promise((resolve) => csvResponses.push(resolve));
  };
  const mainPath = path.resolve(__dirname, "../../.dashboard-test-build/main.js");
  delete require.cache[mainPath];
  require(mainPath);
  t.after(() => {
    delete require.cache[mainPath];
    global.document = originalDocument;
    global.fetch = originalFetch;
  });

  await new Promise(setImmediate);
  assert.equal(csvResponses.length, 1);
  assert.equal(elements.plot.hidden, true);
  assert.equal(elements.data.hidden, true);

  csvResponses[0]({ ok: true, text: async () => "metric,value\nfirst,0.42\n" });
  await new Promise(setImmediate);
  assert.equal(elements.plot.src, "https://example.test/figures/first.svg");
  assert.equal(elements.data.children.length, 0);
  assert.equal(elements.plot.hidden, true);
  assert.equal(elements.data.hidden, true);

  elements.figure.value = "second";
  elements.figure.dispatch("change");
  assert.equal(elements.plot.hidden, true);
  assert.equal(elements.data.hidden, true);
  assert.equal(csvResponses.length, 2);

  elements.plot.dispatch("load");
  assert.equal(elements.data.children.length, 0);
  assert.equal(elements.plot.hidden, true);
  assert.equal(elements.data.hidden, true);

  csvResponses[1]({ ok: true, text: async () => "metric,value\nsecond,0.57\n" });
  await new Promise(setImmediate);
  assert.equal(elements.plot.src, "https://example.test/figures/second.svg");
  assert.equal(elements.data.children.length, 0);
  assert.equal(elements.plot.hidden, true);
  assert.equal(elements.data.hidden, true);

  elements.plot.dispatch("load");
  assert.equal(elements.data.children[1].children[0].textContent, "second");
  assert.equal(elements.plot.hidden, false);
  assert.equal(elements.data.hidden, false);
});

import {
  buildPages,
  figureCaption,
  figuresFor,
  formatTable,
  parseCsv,
  parseSelectorValue,
  queryToState,
  selectorLabel,
  selectorOptions,
  selectorsFor,
  selectorValue,
  settleSelection,
  stateToQuery,
  type Canon,
  type Figure,
  type Page,
  type Selection,
} from "./viewer.js";

const base = new URL(document.baseURI);
const elements = {
  pages: document.querySelector<HTMLElement>("#pages")!,
  selectors: document.querySelector<HTMLFormElement>("#selectors")!,
  figures: document.querySelector<HTMLElement>("#figures")!,
  error: document.querySelector<HTMLElement>("#error")!,
};
const selectorNames: Record<string, string> = {
  forcing: "Forcing", pcorr: "Precipitation correction", model: "Model", goal: "Calibration goal",
};

async function load<T>(name: string, fallback?: T): Promise<T> {
  const response = await fetch(new URL(name, base));
  if (!response.ok) {
    if (fallback !== undefined) return fallback;
    throw new Error(`Could not load ${name}.`);
  }
  return response.json() as Promise<T>;
}

function element<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderTable(table: HTMLTableElement, csv: string): void {
  table.replaceChildren(...formatTable(parseCsv(csv)).map((row, rowIndex) => {
    const tr = element("tr");
    tr.append(...row.map((value) => element(rowIndex === 0 ? "th" : "td", value)));
    return tr;
  }));
}

/** A full-width figure with its data table folded below; the CSV loads when first opened. */
function figureBlock(figure: Figure): HTMLElement {
  const block = element("figure");
  const image = element("img");
  image.src = new URL(figure.svg, base).toString();
  image.alt = figureCaption(figure);
  image.loading = "lazy";
  const caption = element("figcaption", figureCaption(figure));
  const details = element("details");
  const summary = element("summary", "Data table");
  const download = element("a", "Download CSV");
  download.href = new URL(figure.csv, base).toString();
  download.setAttribute("download", "");
  const table = element("table");
  details.append(summary, download, table);
  let loaded = false;
  details.addEventListener("toggle", () => {
    if (!details.open || loaded) return;
    loaded = true;
    fetch(new URL(figure.csv, base))
      .then((response) => {
        if (!response.ok) throw new Error(`Could not load ${figure.csv}`);
        return response.text();
      })
      .then((csv) => renderTable(table, csv))
      .catch((error: Error) => {
        loaded = false;
        table.replaceChildren(element("caption", error.message));
      });
  });
  block.append(image, caption, details);
  return block;
}

function render(pages: Page[], pageKey: string | undefined, wanted: Selection): void {
  const page = pages.find((candidate) => candidate.key === pageKey) ?? pages[0];
  const selection = settleSelection(page, wanted);
  history.replaceState(null, "", stateToQuery({ page: page.key, selection }));

  elements.pages.replaceChildren(...pages.map((candidate) => {
    const link = element("a", candidate.title);
    link.href = stateToQuery({ page: candidate.key, selection });
    if (candidate.key === page.key) link.setAttribute("aria-current", "page");
    link.addEventListener("click", (event) => {
      event.preventDefault();
      render(pages, candidate.key, selection);
    });
    return link;
  }));

  elements.selectors.replaceChildren(...selectorsFor(page).flatMap((key) => {
    const options = selectorOptions(page, key, selection);
    if (options.length < 2) return [];
    const label = element("label", selectorNames[key]);
    const select = element("select");
    select.replaceChildren(...options.map((value) => {
      const option = element("option", selectorLabel(key, value));
      option.value = selectorValue(value);
      return option;
    }));
    select.value = selectorValue(selection[key] ?? null);
    select.addEventListener("change", () =>
      render(pages, page.key, { ...selection, [key]: parseSelectorValue(key, select.value) }));
    label.append(select);
    return [label];
  }));

  elements.figures.replaceChildren(...figuresFor(page, selection).map(figureBlock));
}

async function start(): Promise<void> {
  try {
    const [index, canon] = await Promise.all([
      load<{ figures: Figure[] }>("figure-index.json"),
      load<Canon>("canon.json", {}),
    ]);
    const pages = buildPages(canon, index.figures);
    if (!pages.length) throw new Error("No figure is published yet.");
    const state = queryToState(location.search);
    render(pages, state.page, state.selection ?? {});
  } catch (error) {
    elements.error.textContent = error instanceof Error ? error.message : "Could not load the figures.";
  }
}

void start();

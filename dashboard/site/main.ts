import {
  parseCsv,
  parseSelectorValue,
  resolveFigures,
  selectorOptions,
  selectorValue,
  type Figure,
  type SelectorKey,
  type Selection,
} from "./viewer.js";

const selectors: SelectorKey[] = ["forcing", "direction", "pcorr", "optimizer"];
const indexUrl = new URL("figure-index.json", document.baseURI);
let renderVersion = 0;
const elements = {
  forcing: document.querySelector<HTMLSelectElement>("#forcing")!,
  direction: document.querySelector<HTMLSelectElement>("#direction")!,
  pcorr: document.querySelector<HTMLSelectElement>("#pcorr")!,
  optimizer: document.querySelector<HTMLSelectElement>("#optimizer")!,
  figure: document.querySelector<HTMLSelectElement>("#figure")!,
  plot: document.querySelector<HTMLImageElement>("#plot")!,
  table: document.querySelector<HTMLTableElement>("#data")!,
  error: document.querySelector<HTMLElement>("#error")!,
};

function optionsFor(select: HTMLSelectElement, values: (string | boolean | null)[]): void {
  select.replaceChildren(...values.map((value) => {
    const option = document.createElement("option");
    option.value = selectorValue(value);
    option.textContent = value === null ? "All" : value === true ? "On" : value === false ? "Off" : value;
    return option;
  }));
}

function selectionFromForm(): Partial<Selection> {
  const selection: Partial<Selection> = {};
  for (const key of selectors) {
    const select = elements[key];
    if (select.value !== "") selection[key] = parseSelectorValue(key, select.value) as never;
  }
  return selection;
}

function renderTable(csv: string): void {
  const rows = parseCsv(csv);
  elements.table.replaceChildren();
  rows.forEach((row, rowIndex) => {
    const tr = document.createElement("tr");
    row.forEach((value) => {
      const cell = document.createElement(rowIndex === 0 ? "th" : "td");
      cell.textContent = value;
      tr.append(cell);
    });
    elements.table.append(tr);
  });
}

function render(figures: Figure[]): void {
  const currentRender = ++renderVersion;
  elements.plot.hidden = true;
  elements.table.hidden = true;
  let selection = selectionFromForm();
  for (const key of selectors) {
    const values = selectorOptions(figures, key, selection);
    const select = elements[key];
    optionsFor(select, values);
    const prior = selectorValue(selection[key] ?? null);
    select.value = values.some((value) => selectorValue(value) === prior)
      ? prior
      : values.length ? selectorValue(values[0]) : "";
    selection[key] = values.length ? parseSelectorValue(key, select.value) as never : undefined;
  }

  const matches = resolveFigures(figures, selection as Selection);
  const previousFigure = elements.figure.value;
  elements.figure.replaceChildren(...matches.map((figure) => {
    const option = document.createElement("option");
    option.value = figure.id;
    option.textContent = figure.view;
    return option;
  }));
  if (matches.some((figure) => figure.id === previousFigure)) elements.figure.value = previousFigure;
  const chosen = matches.find((figure) => figure.id === elements.figure.value) ?? matches[0];
  if (!chosen) {
    elements.plot.removeAttribute("src");
    elements.table.replaceChildren();
    elements.error.textContent = "No figure is declared for this selection.";
    return;
  }
  elements.error.textContent = "";
  fetch(new URL(chosen.csv, indexUrl))
    .then((response) => {
      if (!response.ok) throw new Error(`Could not load ${chosen.csv}`);
      return response.text();
    })
    .then((csv) => {
      if (currentRender !== renderVersion) return;
      const imageUrl = new URL(chosen.svg, indexUrl).toString();
      elements.plot.addEventListener("load", () => {
        if (currentRender !== renderVersion) return;
        renderTable(csv);
        elements.plot.hidden = false;
        elements.table.hidden = false;
      }, { once: true });
      elements.plot.addEventListener("error", () => {
        if (currentRender !== renderVersion) return;
        elements.table.replaceChildren();
        elements.error.textContent = `Could not load ${chosen.svg}`;
      }, { once: true });
      elements.plot.src = imageUrl;
    })
    .catch((error: Error) => {
      if (currentRender !== renderVersion) return;
      elements.table.replaceChildren();
      elements.error.textContent = error.message;
    });
}

async function start(): Promise<void> {
  try {
    const response = await fetch(indexUrl);
    if (!response.ok) throw new Error("Could not load the figure index.");
    const index = await response.json() as { figures: Figure[] };
    const figures = index.figures;
    selectors.forEach((key) => elements[key].addEventListener("change", () => render(figures)));
    elements.figure.addEventListener("change", () => render(figures));
    render(figures);
  } catch (error) {
    elements.error.textContent = error instanceof Error ? error.message : "Could not load the figure index.";
  }
}

void start();

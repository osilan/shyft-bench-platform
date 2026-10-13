// Pure logic of the dashboard (bench.dashboard, D-032): pages, selectors, figure choice,
// number formatting and URL state. main.ts only draws what these functions return.

/** One published figure, as listed in figure-index.json. */
export interface Figure {
  id: string;
  view: string;
  forcing: string;
  direction: string | null;
  pcorr: boolean | null;
  optimizer: string;
  svg: string;
  csv: string;
  /** From canon.json pageFigures: the model or goal a page selector picks, if any. */
  model?: string | null;
  goal?: string | null;
}

/** A page as exported from Lean (canon.json `pages`). */
export interface PageSpec {
  key: string;
  title: string;
  status: string;
  selectors: string[];
  figures: string[];
}

export interface PageFigureSpec {
  id: string;
  model: string | null;
  goal: string | null;
}

export interface Canon {
  pages?: PageSpec[];
  pageFigures?: PageFigureSpec[];
}

/** Forcing first, then the page's own selectors. */
export type SelectorKey = "forcing" | "pcorr" | "model" | "goal";
export type SelectorValue = string | boolean | null;
export type Selection = Partial<Record<SelectorKey, SelectorValue>>;

export interface Page {
  key: string;
  title: string;
  selectors: SelectorKey[];
  figures: Figure[];
}

/** Figures in the index that belong to no page, during the switch to pages (D-032). */
export const OTHER_PAGE_KEY = "other";
const PAGE_SELECTORS: SelectorKey[] = ["pcorr", "model", "goal"];

function isPageSelector(key: string): key is SelectorKey {
  return (PAGE_SELECTORS as string[]).includes(key);
}

/**
 * The menu: every published page with at least one built figure, in Lean's order, then an
 * "Other figures" page for built figures that no page declares. A declared figure that is not
 * in the index yet is skipped; a page with none built yet is left out; a planned page and its
 * figures are hidden.
 */
export function buildPages(canon: Canon, index: Figure[]): Page[] {
  const byId = new Map(index.map((figure) => [figure.id, figure]));
  const pageFigure = new Map((canon.pageFigures ?? []).map((spec) => [spec.id, spec]));
  // Figures of planned pages stay hidden too, so they never fall through to "Other figures".
  const onPages = new Set((canon.pages ?? []).flatMap((spec) => spec.figures));
  const pages: Page[] = [];
  for (const spec of canon.pages ?? []) {
    if (spec.status !== "published") continue;
    const figures = spec.figures.flatMap((id) => {
      const figure = byId.get(id);
      if (!figure) return [];
      const extra = pageFigure.get(id);
      return [{ ...figure, model: extra?.model ?? null, goal: extra?.goal ?? null }];
    });
    if (figures.length) {
      pages.push({ key: spec.key, title: spec.title, selectors: spec.selectors.filter(isPageSelector), figures });
    }
  }
  const others = index.filter((figure) => !onPages.has(figure.id));
  if (others.length) {
    const selectors = PAGE_SELECTORS.filter((key) => new Set(others.map((f) => f[key] ?? null)).size > 1);
    pages.push({ key: OTHER_PAGE_KEY, title: "Other figures", selectors, figures: others });
  }
  return pages;
}

export function selectorsFor(page: Page): SelectorKey[] {
  return ["forcing", ...page.selectors];
}

function valueOf(figure: Figure, key: SelectorKey): SelectorValue {
  return figure[key] ?? null;
}

/** A figure matches when every selector agrees, or the figure does not vary on it (null). */
function matches(figure: Figure, selection: Selection, keys: SelectorKey[]): boolean {
  return keys.every((key) => {
    const value = valueOf(figure, key);
    return value === null || selection[key] === undefined || value === selection[key];
  });
}

/** Options of one selector, given the selectors before it. Null values are not options. */
export function selectorOptions(page: Page, key: SelectorKey, selection: Selection): SelectorValue[] {
  const keys = selectorsFor(page);
  const before = keys.slice(0, keys.indexOf(key));
  const values = page.figures
    .filter((figure) => matches(figure, selection, before))
    .map((figure) => valueOf(figure, key))
    .filter((value) => value !== null);
  return [...new Set(values)];
}

/** Keep each chosen value if it is still an option, otherwise take the first option. */
export function settleSelection(page: Page, wanted: Selection): Selection {
  const selection: Selection = {};
  for (const key of selectorsFor(page)) {
    const options = selectorOptions(page, key, selection);
    if (!options.length) continue;
    selection[key] = options.some((value) => value === wanted[key]) ? wanted[key] : options[0];
  }
  return selection;
}

/** The figures to show for a settled selection, in the page's declared order. */
export function figuresFor(page: Page, selection: Selection): Figure[] {
  return page.figures.filter((figure) => matches(figure, selection, selectorsFor(page)));
}

export function selectorValue(value: SelectorValue): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  return value;
}

export function parseSelectorValue(key: SelectorKey, value: string): SelectorValue {
  if (value === "null") return null;
  if (key === "pcorr") return value === "true";
  return value;
}

export function selectorLabel(key: SelectorKey, value: SelectorValue): string {
  if (value === null) return "All";
  if (key === "pcorr") return value ? "On" : "Off";
  return key === "model" ? String(value).toUpperCase() : String(value);
}

/** A one-line description of what a figure holds, from its declared fields. */
export function figureCaption(figure: Figure): string {
  const parts = [figure.view.replace(/-/g, " "), `forcing ${figure.forcing}`];
  if (figure.direction) parts.push(`${figure.direction}`);
  if (figure.pcorr !== null) parts.push(`pcorr ${figure.pcorr ? "on" : "off"}`);
  parts.push(figure.optimizer.toUpperCase());
  if (figure.model) parts.push(figure.model.toUpperCase());
  if (figure.goal) parts.push(`goal ${figure.goal}`);
  return parts.join(" · ");
}

/** Display a table cell: numbers rounded to three significant digits, text unchanged. */
export function formatCell(text: string): string {
  const trimmed = text.trim();
  if (trimmed === "" || !/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(trimmed)) return text;
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return text;
  if (Number.isInteger(value) && Math.abs(value) < 1e6) return String(value);
  return String(Number(value.toPrecision(3)));
}

/** Identifier columns keep their text: a station id like 109.29 is not a number to round. */
export function isIdentifierColumn(header: string): boolean {
  return /(^|_)(id|station|stid|model|goal|metric|seed)$/i.test(header.trim());
}

/** The table as displayed: header unchanged, numeric cells rounded except in identifier columns. */
export function formatTable(rows: string[][]): string[][] {
  if (!rows.length) return rows;
  const [header, ...body] = rows;
  const keep = header.map(isIdentifierColumn);
  return [header, ...body.map((row) => row.map((cell, i) => (keep[i] ? cell : formatCell(cell))))];
}

export interface ViewState {
  page: string;
  selection: Selection;
}

export function stateToQuery(state: ViewState): string {
  const params = new URLSearchParams({ page: state.page });
  for (const key of ["forcing", ...PAGE_SELECTORS] as SelectorKey[]) {
    const value = state.selection[key];
    if (value !== undefined) params.set(key, selectorValue(value));
  }
  return `?${params.toString()}`;
}

export function queryToState(query: string): Partial<ViewState> {
  const params = new URLSearchParams(query);
  const selection: Selection = {};
  for (const key of ["forcing", ...PAGE_SELECTORS] as SelectorKey[]) {
    const raw = params.get(key);
    if (raw !== null) selection[key] = parseSelectorValue(key, raw);
  }
  const page = params.get("page");
  return page === null ? { selection } : { page, selection };
}

export function parseCsv(csv: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < csv.length; i += 1) {
    const char = csv[i];
    if (char === '"' && quoted && csv[i + 1] === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && csv[i + 1] === "\n") i += 1;
      row.push(cell);
      if (row.some((item) => item !== "")) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell !== "" || row.length > 0) {
    row.push(cell);
    if (row.some((item) => item !== "")) rows.push(row);
  }
  return rows;
}

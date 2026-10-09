export interface Figure {
  id: string;
  view: string;
  forcing: string;
  direction: string | null;
  pcorr: boolean | null;
  optimizer: string;
  svg: string;
  csv: string;
}

export type SelectorKey = "forcing" | "direction" | "pcorr" | "optimizer";
export type SelectorValue = string | boolean | null;
export type Selection = Pick<Figure, SelectorKey>;

const selectorOrder: SelectorKey[] = ["forcing", "direction", "pcorr", "optimizer"];

export function selectorOptions(
  figures: Figure[],
  key: SelectorKey,
  selection: Partial<Selection>,
): SelectorValue[] {
  const keyIndex = selectorOrder.indexOf(key);
  const candidates = figures.filter((figure) =>
    selectorOrder.slice(0, keyIndex).every((previous) =>
      selection[previous] === undefined || figure[previous] === selection[previous],
    ),
  );
  return [...new Set(candidates.map((figure) => figure[key]))];
}

export function resolveFigures(figures: Figure[], selection: Selection): Figure[] {
  return figures.filter((figure) =>
    selectorOrder.every((key) => figure[key] === selection[key]),
  );
}

export function selectorValue(value: SelectorValue): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  return value;
}

export function parseSelectorValue(key: SelectorKey, value: string): string | boolean | null {
  if (value === "null") return null;
  if (key === "pcorr") return value === "true";
  return value;
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

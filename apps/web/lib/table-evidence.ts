/**
 * The table cell behind an X401 card (Codex review #7): the engine sends
 * `table_evidence` when a sentence names a row and a column and the number
 * it quotes is not the one in that cell. Pure helpers, unit-tested in
 * tests/unit/table-evidence.test.tsx.
 */
import type { Suggestion, TableEvidence } from "@researchly/contract";

/** Highlight ids for a cell carry this suffix, so they never clash with a suggestion's id. */
const CELL_SUFFIX = "~cell";

export function cellId(suggestionId: string): string {
  return `${suggestionId}${CELL_SUFFIX}`;
}

/** The suggestion a highlight id belongs to: a cell's id maps back to its card. */
export function baseId(id: string): string {
  return id.endsWith(CELL_SUFFIX) ? id.slice(0, -CELL_SUFFIX.length) : id;
}

export function evidenceOf(s: Pick<Suggestion, "table_evidence">): TableEvidence | null {
  return s.table_evidence ?? null;
}

/**
 * The cell as a highlight: a stand-in suggestion with the cell's id, span
 * and text, for resolveSpans(). Null without evidence or with an unusable span.
 */
export function cellHighlight(s: Suggestion): Suggestion | null {
  const ev = evidenceOf(s);
  if (!ev || !(ev.cell_end > ev.cell_start)) return null;
  return {
    ...s,
    id: cellId(s.id),
    span: { ...s.span, start: ev.cell_start, end: ev.cell_end },
    text: ev.cell_text,
    table_evidence: null,
  };
}

/** "Table 1, row “Mortality”, column “Treatment”". */
export function cellPlace(ev: TableEvidence): string {
  const parts = [ev.table.trim() || "The table"];
  if (ev.row_header.trim()) parts.push(`row “${ev.row_header.trim()}”`);
  if (ev.column_header.trim()) parts.push(`column “${ev.column_header.trim()}”`);
  return parts.join(", ");
}

/** The rounding the comparison allowed, as a sentence, or null for none. */
export function roundingNote(ev: TableEvidence): string | null {
  const r = (ev.rounding ?? "").trim();
  return r ? `Compared ${r}, so a rounded value would still match.` : null;
}

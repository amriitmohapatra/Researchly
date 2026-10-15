/**
 * Every Office.js call the Word taskpane makes, in one place (S3).
 *
 * - The rest of the app never touches `Office` or `Word`: it calls these
 *   functions with an `OfficeApi`, which tests replace with a fake
 *   (e2e/fake-office.ts serves the same fake as office.js in the browser).
 * - Word has no character offsets. A suggestion is found again by searching
 *   its paragraph for the engine's `snippet` and taking match number
 *   `occurrence` (contract `WordLocation`, built by researchly.wordloc).
 *   Before anything is selected or replaced, the paragraph is re-read and
 *   checked to still hold that text at that place; an edit is refused rather
 *   than guessed.
 * - Tracked changes are used only where Word supports them (WordApi 1.4).
 *   Setting `changeTrackingMode` on an older Word does not throw: it fails
 *   the whole batch at sync, silently. So it is never set there.
 *
 * Offsets in a `WordLocation` are Unicode code points (Python indices);
 * JavaScript strings are UTF-16, so slicing goes through `codePointSlice`.
 */
import type { WordLocation, WordParagraph } from "@researchly/contract";

/* ---------- the slice of the Office.js API this app uses (structural, so a fake can stand in) ---------- */

export interface OfficeFieldCollection {
  items: unknown[];
  load(props?: string): void;
}

export interface OfficeRange {
  text: string;
  load(props?: string): void;
  select(selectionMode?: string): void;
  insertText(text: string, insertLocation: string): unknown;
  /** WordApi 1.4+ only. */
  fields?: OfficeFieldCollection;
  /** A sub-range: "Start", "End", "Whole". */
  getRange(rangeLocation?: string): OfficeRange;
  /** The range from the earlier start to the later end of the two. */
  expandTo(range: OfficeRange): OfficeRange;
  /** The paragraphs this range touches. */
  paragraphs: OfficeParagraphCollection;
}

export interface OfficeRangeCollection {
  items: OfficeRange[];
  load(props?: string): void;
}

/** WordApi 1.3+ only. */
export interface OfficeTableRow {
  cellCount: number;
  load(props?: string): void;
}

/** WordApi 1.3+ only. `rowIndex` and `cellIndex` count cells along the row, 0-based. */
export interface OfficeTableCell {
  isNullObject?: boolean;
  rowIndex: number;
  cellIndex: number;
  parentRow: OfficeTableRow;
  load(props?: string): void;
}

export interface OfficeParagraph {
  text: string;
  style: string;
  styleBuiltIn?: string;
  tableNestingLevel?: number;
  /** WordApi 1.6+ only: Word's own id for the paragraph, stable while the document is open. */
  uniqueLocalId?: string;
  /** WordApi 1.7+ only (S4d R4): underline ranges of this paragraph; the ids arrive at sync. */
  insertAnnotations?(set: { critiques: OfficeCritique[] }): { value: string[] };
  /** WordApi 1.7+ only. */
  getAnnotations?(): OfficeAnnotationCollection;
  /** WordApi 1.3+ only: the table cell this paragraph is in (a null object outside tables). */
  parentTableCellOrNullObject?: OfficeTableCell;
  search(searchText: string, options: { matchCase: boolean }): OfficeRangeCollection;
}

/** A Word critique (WordApi 1.7): a coloured underline over `start`..`start+length` (UTF-16) of a paragraph. */
export interface OfficeCritique {
  colorScheme: string;
  start: number;
  length: number;
  /** WordApi 1.8+ only: the popup's manifest string resources and up to three revisions. */
  popupOptions?: {
    brandingTextResourceId: string;
    titleResourceId: string;
    subtitleResourceId: string;
    suggestions: string[];
  };
}

/** WordApi 1.7+ only. */
export interface OfficeAnnotation {
  id: string;
  state?: string;
  critiqueAnnotation: { accept(): void; reject(): void };
  delete(): void;
  load(props?: string): void;
}

export interface OfficeAnnotationCollection {
  items: OfficeAnnotation[];
  load(props?: string): void;
}

/** An Office.js event source on the document (`context.document.onX.add(handler)`). */
export interface OfficeEventSource<T> {
  add(handler: (args: T) => Promise<unknown> | void): unknown;
}

export interface OfficeParagraphCollection {
  items: OfficeParagraph[];
  load(props?: string): void;
}

export interface WordRequestContext {
  document: {
    body: { paragraphs: OfficeParagraphCollection; getRange(rangeLocation?: string): OfficeRange };
    changeTrackingMode: string;
    load(props: string): void;
    /** The current selection, or the insertion point. */
    getSelection(): OfficeRange;
    /** WordApi 1.7+ only (S4d R4). */
    getAnnotationById?(id: string): OfficeAnnotation;
    onAnnotationClicked?: OfficeEventSource<{ id: string }>;
    onAnnotationHovered?: OfficeEventSource<{ id: string }>;
    /** WordApi 1.8+ only: Accept (with the chosen revision) or Reject in the underline's popup. */
    onAnnotationPopupAction?: OfficeEventSource<{ id: string; action: string; critiqueSuggestion?: string }>;
    /** WordApi 1.6+ only. */
    onParagraphChanged?: OfficeEventSource<{ uniqueLocalIds?: string[] }>;
    onParagraphAdded?: OfficeEventSource<{ uniqueLocalIds?: string[] }>;
    onParagraphDeleted?: OfficeEventSource<{ uniqueLocalIds?: string[] }>;
  };
  sync(): Promise<unknown>;
}

export interface OfficeApi {
  Office: {
    onReady(callback?: (info: { host: string | null; platform: string | null }) => void): Promise<{
      host: string | null;
      platform: string | null;
    }>;
    context: {
      requirements: { isSetSupported(name: string, minVersion?: string): boolean };
      /** The common API's document: where Word without paragraph events reports a moved selection (any edit moves it). */
      document?: { addHandlerAsync?(eventType: string, handler: () => void, callback?: (result: unknown) => void): void };
    };
    EventType?: { DocumentSelectionChanged: string };
  };
  Word: {
    run<T>(batch: (context: WordRequestContext) => Promise<T>): Promise<T>;
  };
}

/* ---------- loading ---------- */

type HistoryFns = { pushState: History["pushState"]; replaceState: History["replaceState"] };

/**
 * office.js sets `history.pushState` and `replaceState` to null in some
 * hosts, which breaks Next.js's router. public/word/office-guard.js saves
 * them before office.js runs and office-restore.js puts them back; this
 * repeats the restore once Office is ready, in case office.js removed them
 * again later.
 */
export function restoreHistory(win: Window & { __researchlyHistory?: HistoryFns } = window): void {
  const saved = win.__researchlyHistory;
  if (!saved || !win.history) return;
  if (typeof win.history.pushState !== "function") win.history.pushState = saved.pushState;
  if (typeof win.history.replaceState !== "function") win.history.replaceState = saved.replaceState;
}

/**
 * The real Office.js globals, once Word is ready. `Word` does not exist when
 * office.js first runs: office.js fetches the host's own scripts and defines
 * `Word` only inside Word, before Office.onReady resolves. Use
 * waitForOffice() first; this is for the actions that come after.
 */
export function officeApi(): OfficeApi | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { Office?: OfficeApi["Office"]; Word?: OfficeApi["Word"] };
  return w.Office && typeof w.Office.onReady === "function" && w.Word ? { Office: w.Office, Word: w.Word } : null;
}

/** office.js's `Office` object alone: what exists as soon as office.js has run, in Word or in a browser. */
export type OfficeGlobal = Pick<OfficeApi, "Office">;

export function officeGlobal(): OfficeGlobal | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { Office?: OfficeApi["Office"] };
  return w.Office && typeof w.Office.onReady === "function" ? { Office: w.Office } : null;
}

export type HostStatus =
  /** Running inside Word. `trackChanges`: fixes can be applied as tracked changes (WordApi 1.4). */
  | { status: "word"; trackChanges: boolean }
  /** office.js loaded, but this page was opened in a browser or another Office app. */
  | { status: "not_word" }
  /** office.js never arrived (blocked, offline) or never became ready. */
  | { status: "unavailable" };

/** Whether this Word supports WordApi `version`; false when it cannot say. */
export function wordApiAtLeast(api: OfficeApi, version: string): boolean {
  try {
    return api.Office.context.requirements.isSetSupported("WordApi", version);
  } catch {
    return false;
  }
}

export function canTrackChanges(api: OfficeApi): boolean {
  return wordApiAtLeast(api, "1.4");
}

/**
 * Wait for Office to say where it is running. Never rejects.
 *
 * `office` is office.js's `Office` object (officeGlobal()); `Word` is looked
 * up only after Office is ready, because office.js defines it late and only
 * inside Word. Checking for `Word` up front made every real load look like a
 * failed one (the fake Office.js defined `Word` at once, so tests passed).
 */
export async function waitForOffice(
  office: OfficeGlobal | null,
  timeoutMs = 10_000,
  wordApi: () => OfficeApi | null = officeApi,
): Promise<HostStatus> {
  if (!office) return { status: "unavailable" };
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<null>((resolve) => {
    timer = setTimeout(() => resolve(null), timeoutMs);
  });
  try {
    const info = await Promise.race([office.Office.onReady(), timeout]);
    if (!info) return { status: "unavailable" };
    if (info.host !== "Word") return { status: "not_word" };
    const api = wordApi();
    if (!api) return { status: "unavailable" };
    return { status: "word", trackChanges: canTrackChanges(api) };
  } catch {
    return { status: "unavailable" };
  } finally {
    clearTimeout(timer);
  }
}

/* ---------- text helpers (pure) ---------- */

/** Python-style `text[start:end]` by code point. */
export function codePointSlice(text: string, start: number, end: number): string {
  return Array.from(text).slice(start, end).join("");
}

/** Python's `str.count`: non-overlapping matches, left to right. */
export function countOccurrences(text: string, needle: string): number {
  if (!needle) return 0;
  let n = 0;
  for (let i = text.indexOf(needle); i >= 0; i = text.indexOf(needle, i + needle.length)) n++;
  return n;
}

const MAX_STYLE = 200; // the contract's limit on WordParagraph.style

/** One Office paragraph as the engine reads it: text, style, and whether it is a table cell. */
export function toWordParagraph(p: {
  text?: string | null;
  style?: string | null;
  styleBuiltIn?: string | null;
  tableNestingLevel?: number | null;
}): WordParagraph {
  // Built-in styles have a locale-independent name ("Heading1" in a French
  // Word too); custom ones only have their display name.
  const builtIn = p.styleBuiltIn && p.styleBuiltIn !== "Other" ? p.styleBuiltIn : "";
  return {
    text: p.text ?? "",
    style: (builtIn || p.style || "").slice(0, MAX_STYLE),
    // Table cells are not prose: counted as prose they skewed the metrics,
    // and a cell reading "Methods" could re-section the rest of the document.
    kind: (p.tableNestingLevel ?? 0) > 0 ? "table" : "body",
  };
}

/* ---------- reading ---------- */

/**
 * The document body's paragraphs, in order (footnotes, headers and text
 * boxes are not included; countUnread says how many were left out). A table paragraph also carries its `cell` place
 * where Word can report it reliably (readCellPlaces).
 */
export async function readParagraphs(api: OfficeApi): Promise<WordParagraph[]> {
  return (await readParagraphsAndIds(api, false)).paragraphs;
}

/**
 * The paragraphs and, with `withIds` (WordApi 1.6), Word's own id for each
 * (`uniqueLocalId`; null without it). The ids are never sent to the engine
 * with the full check: they let the underlines (S4d R4) follow a paragraph
 * that moved.
 */
export function readParagraphsAndIds(
  api: OfficeApi,
  withIds: boolean,
): Promise<{ paragraphs: WordParagraph[]; ids: (string | null)[] }> {
  return api.Word.run(async (ctx) => {
    const paras = ctx.document.body.paragraphs;
    paras.load(`items/text,items/style,items/styleBuiltIn,items/tableNestingLevel${withIds ? ",items/uniqueLocalId" : ""}`);
    await ctx.sync();
    const out = paras.items.map((p) => toWordParagraph(p));
    const places = await readCellPlaces(api, ctx, paras.items);
    places.forEach((cell, i) => {
      if (cell && out[i]) out[i].cell = cell;
    });
    return { paragraphs: out, ids: paras.items.map((p) => (withIds ? (p.uniqueLocalId ?? null) : null)) };
  });
}

/* ---------- what the check does not read (the coverage summary, Codex review #5) ---------- */

/** A part of the document the check did not read, counted: the reading line's "Not checked: 2 footnotes". */
export interface UnreadPart {
  kind: "footnotes" | "endnotes" | "comments" | "text_boxes";
  count: number;
  label: string;
}

/** A collection Word can count without reading text: only `items` with one non-text property is loaded. */
interface CountableCollection {
  items: { type?: string }[];
  load(props: string): void;
}

/** The parts of WordApi that count notes, comments and shapes; absent on older Word. */
interface CountableBody {
  footnotes?: CountableCollection;
  endnotes?: CountableCollection;
  shapes?: CountableCollection;
  getComments?(): CountableCollection;
}

const UNREAD_LABELS: Record<UnreadPart["kind"], string> = {
  footnotes: "footnotes",
  endnotes: "endnotes",
  comments: "comments",
  text_boxes: "text boxes",
};

function apiAtLeast(api: OfficeApi, set: string, version: string): boolean {
  try {
    return api.Office.context.requirements.isSetSupported(set, version);
  } catch {
    return false;
  }
}

/**
 * The check reads the document body's paragraphs only. This counts what it
 * leaves out, where Word can count it without handing over any text:
 * footnotes and endnotes (WordApi 1.5), comments (1.4) and text boxes
 * (WordApiDesktop 1.2). Each count is its own batch, so a Word that refuses
 * one still gives the others; a Word without the API gives none. Never
 * throws; never reads a word of text. Headers and footers are not counted:
 * Word cannot tell an empty one from a full one without reading it.
 */
export async function countUnread(api: OfficeApi): Promise<UnreadPart[]> {
  const count = async (kind: UnreadPart["kind"], pick: (body: CountableBody) => CountableCollection | undefined, keep: (item: { type?: string }) => boolean = () => true) => {
    try {
      return await api.Word.run(async (ctx) => {
        const coll = pick(ctx.document.body as unknown as CountableBody);
        if (!coll) return null;
        coll.load(kind === "comments" ? "items/id" : "items/type");
        await ctx.sync();
        const n = coll.items.filter(keep).length;
        return n > 0 ? { kind, count: n, label: UNREAD_LABELS[kind] } : null;
      });
    } catch {
      return null; // a host that cannot count this part loses nothing else
    }
  };
  const tasks: Promise<UnreadPart | null>[] = [];
  if (apiAtLeast(api, "WordApi", "1.5")) {
    tasks.push(count("footnotes", (b) => b.footnotes));
    tasks.push(count("endnotes", (b) => b.endnotes));
  }
  if (apiAtLeast(api, "WordApi", "1.4")) tasks.push(count("comments", (b) => b.getComments?.()));
  if (apiAtLeast(api, "WordApiDesktop", "1.2")) tasks.push(count("text_boxes", (b) => b.shapes, (s) => s.type === "TextBox"));
  return (await Promise.all(tasks)).filter((p): p is UnreadPart => p !== null);
}

/* ---------- table cell places (X401, Codex review #7) ---------- */

/** The contract's bound on a table, row or column number (`WordParagraph.cell`; the service's MAX_CELL_INDEX). */
export const MAX_CELL_INDEX = 100_000;

/** `[table, row, col]`, 0-based: where a table paragraph sits. */
export type CellPlace = [number, number, number];

/**
 * What Word reports for one paragraph: `level` (tableNestingLevel), `row`
 * and `cell` (its cell's rowIndex and cellIndex) and `cells` (its row's
 * cellCount). The last three are missing where Word could not place it.
 */
export interface CellReport {
  level: number;
  row?: number;
  cell?: number;
  cells?: number;
}

/** Cell places need `Paragraph.parentTableCellOrNullObject`, `TableCell.parentRow` and `TableRow.cellCount`: WordApi 1.3. */
export function canPlaceCells(api: OfficeApi): boolean {
  return wordApiAtLeast(api, "1.3");
}

/**
 * Cell places from what Word reports per paragraph: `[table, row, col]` or
 * null for each.
 *
 * Tables are numbered in order. Word joins two tables with nothing between
 * them into one, so a run of consecutive table paragraphs is one table.
 * cellIndex counts cells along the row, not grid columns: a horizontally
 * merged cell shifts every later column. So a table whose rows report
 * different cell counts (merged cells) gets no places at all, as does a
 * table inside a table, or any table with a paragraph Word could not place.
 * Without places the engine checks the whole table: nothing is guessed.
 */
export function tablePlaces(paras: readonly CellReport[]): (CellPlace | null)[] {
  const out: (CellPlace | null)[] = paras.map(() => null);
  let table = -1;
  let i = 0;
  while (i < paras.length) {
    if (!(paras[i]!.level > 0)) {
      i += 1;
      continue;
    }
    let j = i;
    while (j < paras.length && paras[j]!.level > 0) j += 1;
    table += 1;
    const run = paras.slice(i, j);
    if (table <= MAX_CELL_INDEX && placeable(run)) {
      run.forEach((p, k) => {
        out[i + k] = [table, p.row!, p.cell!];
      });
    }
    i = j;
  }
  return out;
}

function placeable(run: readonly CellReport[]): boolean {
  const whole = (n: number | undefined): n is number => Number.isInteger(n) && n! >= 0 && n! <= MAX_CELL_INDEX;
  let count: number | null = null;
  let lastRow = 0;
  for (const p of run) {
    if (p.level !== 1) return false; // a table inside a table
    if (!whole(p.row) || !whole(p.cell) || !whole(p.cells)) return false;
    if (p.cell >= p.cells || p.row < lastRow) return false;
    if (count === null) count = p.cells;
    else if (p.cells !== count) return false; // merged cells
    lastRow = p.row;
  }
  return true;
}

/**
 * Ask Word where each table paragraph sits, inside the reading batch. Never
 * throws: an older Word, a document without tables or any error gives no
 * places (the check goes ahead without them). Reads only cell numbers, no
 * text.
 */
export async function readCellPlaces(
  api: OfficeApi,
  ctx: WordRequestContext,
  items: readonly OfficeParagraph[],
): Promise<(CellPlace | null)[]> {
  const none = items.map(() => null);
  if (!canPlaceCells(api)) return none;
  if (!items.some((p) => (p.tableNestingLevel ?? 0) > 0)) return none;
  try {
    const cells = items.map((p) => ((p.tableNestingLevel ?? 0) > 0 ? (p.parentTableCellOrNullObject ?? null) : null));
    cells.forEach((c) => c?.load("rowIndex,cellIndex"));
    await ctx.sync();
    const rows = cells.map((c) => (c && !c.isNullObject ? c.parentRow : null));
    rows.forEach((r) => r?.load("cellCount"));
    await ctx.sync();
    return tablePlaces(
      items.map((p, i) => {
        const c = rows[i] ? cells[i] : null;
        return {
          level: p.tableNestingLevel ?? 0,
          row: c?.rowIndex,
          cell: c?.cellIndex,
          cells: rows[i]?.cellCount,
        };
      }),
    );
  } catch {
    return none; // a host that cannot report cells loses nothing else
  }
}

/**
 * The index (into `readParagraphs`'s list) of the paragraph the cursor is
 * in. Word has no paragraph numbers, so the range from the start of the
 * body to the selection's start is expanded and its paragraphs counted:
 * one batch, no text read beyond what the check reads anyway.
 */
export function readSelectionParagraph(api: OfficeApi): Promise<number> {
  return api.Word.run(async (ctx) => {
    const cursor = ctx.document.getSelection().getRange("Start");
    const upTo = ctx.document.body.getRange("Start").expandTo(cursor);
    const paras = upTo.paragraphs;
    paras.load("items/style");
    await ctx.sync();
    return Math.max(0, paras.items.length - 1);
  });
}

/* ---------- finding a suggestion again ---------- */

export type ActionResult<T> = ({ ok: true } & T) | { ok: false; message: string };

export const CHANGED_MESSAGE =
  "The document has changed here since the check, so nothing was selected or changed. Check the document again.";
export const NOT_FOUND_MESSAGE =
  "Word could not find this text exactly, so nothing was changed. Check the document again; if this keeps happening, make the change by hand.";
export const APPROXIMATE_APPLY_MESSAGE =
  "This passage is too long for Word to find whole, so the revision can’t be applied safely. Make the change by hand.";
export const RANGE_CHANGED_MESSAGE =
  "The text Word found no longer matches what was checked, so nothing was changed. Check the document again.";
export const FIELD_MESSAGE =
  "This text is part of a citation or another Word field. Changing it here would break the field, so nothing was changed.";
export const WORD_FAILED_MESSAGE = "Word could not do that just now. Nothing was changed; try again.";

/**
 * The range for a suggestion, or why it can't be trusted.
 *
 * Guards, in order: the paragraph still exists; it still holds the flagged
 * text at the recorded offsets; Word's search finds the snippet as many
 * times as the engine counted it (so match number `occurrence` means the
 * same to both); and that match is there.
 */
export async function findRange(
  ctx: WordRequestContext,
  loc: WordLocation,
): Promise<{ ok: true; range: OfficeRange; paragraphText: string } | { ok: false; message: string }> {
  if (!loc.snippet) return { ok: false, message: NOT_FOUND_MESSAGE };
  const paras = ctx.document.body.paragraphs;
  paras.load("items/text");
  await ctx.sync();
  const para = paras.items[loc.paragraph];
  if (!para) return { ok: false, message: CHANGED_MESSAGE };
  const here = codePointSlice(para.text, loc.start, loc.end);
  const still = loc.exact ? here === loc.snippet : here.startsWith(loc.snippet);
  if (!still) return { ok: false, message: CHANGED_MESSAGE };

  const results = para.search(loc.snippet, { matchCase: true });
  results.load("items/text");
  await ctx.sync();
  // Word's search and the engine's count must agree, or "match number N"
  // could point at a different copy of a repeated phrase.
  if (results.items.length !== countOccurrences(para.text, loc.snippet)) return { ok: false, message: NOT_FOUND_MESSAGE };
  const range = results.items[loc.occurrence];
  return range ? { ok: true, range, paragraphText: para.text } : { ok: false, message: NOT_FOUND_MESSAGE };
}

/** Select the flagged words in the document. `approximate`: only the start of a long passage could be matched. */
export async function selectSpan(api: OfficeApi, loc: WordLocation): Promise<ActionResult<{ approximate: boolean }>> {
  try {
    return await api.Word.run(async (ctx) => {
      const found = await findRange(ctx, loc);
      if (!found.ok) return found;
      found.range.select();
      await ctx.sync();
      return { ok: true as const, approximate: !loc.exact };
    });
  } catch {
    return { ok: false, message: WORD_FAILED_MESSAGE };
  }
}

/** Whether a range overlaps a Word field: "unknown" when Word could not say. */
type FieldCheck = "none" | "field" | "unknown";

async function fieldCheck(ctx: WordRequestContext, range: OfficeRange, api: OfficeApi): Promise<FieldCheck> {
  // Fields arrived with WordApi 1.4. An older Word has no fields API at all:
  // there is nothing to ask, and the edit is a direct one the writer can undo.
  if (!canTrackChanges(api) || !range.fields) return "none";
  try {
    range.fields.load("items");
    await ctx.sync();
    return range.fields.items.length > 0 ? "field" : "none";
  } catch {
    // Codex review R3: "could not establish field safety" must never mean "safe to edit".
    return "unknown";
  }
}

/**
 * How an Apply ended. Four outcomes, because "nothing changed" must never be
 * said about an edit that may have happened (Codex review R3):
 * - `applied`: the words were replaced (tracked where Word can);
 * - `restore_failed`: replaced, but the writer's Track Changes setting could
 *   not be put back;
 * - `not_applied`: nothing in the document changed;
 * - `unknown`: Word reported an error after the edit was sent, and the text
 *   no longer reads as it did, so it may or may not have been changed.
 * After `applied`, `restore_failed` or `unknown`, the paragraph's other
 * suggestions are out of date and the surface must say so, not offer a retry.
 */
export type ApplyResult =
  | { ok: true; outcome: "applied"; tracked: boolean }
  | { ok: true; outcome: "restore_failed"; tracked: true; message: string }
  | { ok: false; outcome: "not_applied"; message: string }
  | { ok: false; outcome: "unknown"; message: string };

export const FIELD_UNKNOWN_MESSAGE =
  "Word could not say whether this text is part of a citation or another field, so nothing was changed. Make this change by hand.";
export const RESTORE_FAILED_MESSAGE =
  "The change was made, but Track Changes could not be switched back; check Word’s Review tab.";
export const UNKNOWN_MESSAGE = "Word reported an error after the edit; check the text before trying again.";

const notApplied = (message: string): ApplyResult => ({ ok: false, outcome: "not_applied", message });

/**
 * After a failed edit: is the paragraph exactly as it was? Read in a fresh
 * batch, because the failed one may be unusable. Only an identical paragraph
 * proves nothing changed; anything else (including a failed read) is unknown.
 */
async function unchangedSince(api: OfficeApi, paragraph: number, before: string): Promise<boolean> {
  try {
    return await api.Word.run(async (ctx) => {
      const paras = ctx.document.body.paragraphs;
      paras.load("items/text");
      await ctx.sync();
      return paras.items[paragraph]?.text === before;
    });
  } catch {
    return false;
  }
}

/**
 * Replace the flagged words with the suggested revision, as a tracked change
 * where Word supports it. The writer's own Track Changes setting is restored
 * afterwards.
 *
 * Fails closed: a range Word cannot vouch for (a field probe that failed)
 * is never edited. The steps run as separate batches, so a failure says
 * which side of the edit it happened on: tracking switched on, then the
 * insertion, then tracking restored, then the selection (a failed selection
 * after a good edit is harmless and not reported as a failure).
 */
export async function applyReplacement(api: OfficeApi, loc: WordLocation, replacement: string): Promise<ApplyResult> {
  if (!loc.exact) return notApplied(APPROXIMATE_APPLY_MESSAGE);
  const track = canTrackChanges(api);
  // The paragraph as it was before the edit (a holder: it is set inside the batch).
  const seen: { before: string | null } = { before: null };
  try {
    return await api.Word.run(async (ctx): Promise<ApplyResult> => {
      let range: OfficeRange;
      let prior: string | null = null;
      // Everything up to the insertion: a failure here changed nothing.
      try {
        const found = await findRange(ctx, loc);
        if (!found.ok) return notApplied(found.message);
        range = found.range;
        seen.before = found.paragraphText;
        // Re-read the very range about to be replaced.
        range.load("text");
        await ctx.sync();
        if (range.text !== loc.snippet) return notApplied(RANGE_CHANGED_MESSAGE);
        const fields = await fieldCheck(ctx, range, api);
        if (fields === "field") return notApplied(FIELD_MESSAGE);
        if (fields === "unknown") return notApplied(FIELD_UNKNOWN_MESSAGE);
        if (track) {
          ctx.document.load("changeTrackingMode");
          await ctx.sync();
          prior = ctx.document.changeTrackingMode;
          if (prior !== "TrackAll") {
            ctx.document.changeTrackingMode = "TrackAll";
            await ctx.sync();
          }
        }
      } catch {
        await restoreTracking(ctx, track, prior);
        return notApplied(WORD_FAILED_MESSAGE);
      }

      // The edit itself. If Word reports an error here, the insertion may
      // still have run (a batch can partly succeed): only an unchanged
      // paragraph proves it did not.
      try {
        range.insertText(replacement, "Replace");
        await ctx.sync();
      } catch {
        await restoreTracking(ctx, track, prior);
        const same = seen.before !== null && (await unchangedSince(api, loc.paragraph, seen.before));
        return same ? notApplied(WORD_FAILED_MESSAGE) : { ok: false, outcome: "unknown", message: UNKNOWN_MESSAGE };
      }

      const restored = await restoreTracking(ctx, track, prior);
      try {
        range.select();
        await ctx.sync();
      } catch {
        /* the edit stands; only the selection did not follow it */
      }
      if (!restored) return { ok: true, outcome: "restore_failed", tracked: true, message: RESTORE_FAILED_MESSAGE };
      return { ok: true, outcome: "applied", tracked: track };
    });
  } catch {
    // Word.run itself failed (the host refused the batch). Whether anything
    // ran is unknowable from here, so look before saying "nothing changed".
    if (seen.before === null) return notApplied(WORD_FAILED_MESSAGE);
    const same = await unchangedSince(api, loc.paragraph, seen.before);
    return same ? notApplied(WORD_FAILED_MESSAGE) : { ok: false, outcome: "unknown", message: UNKNOWN_MESSAGE };
  }
}

/** Put the writer's Track Changes setting back. False when Word refused; never throws. */
async function restoreTracking(ctx: WordRequestContext, track: boolean, prior: string | null): Promise<boolean> {
  if (!track || prior === null || prior === "TrackAll") return true;
  try {
    ctx.document.changeTrackingMode = prior;
    await ctx.sync();
    return true;
  } catch {
    return false;
  }
}

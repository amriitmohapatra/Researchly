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
}

export interface OfficeRangeCollection {
  items: OfficeRange[];
  load(props?: string): void;
}

export interface OfficeParagraph {
  text: string;
  style: string;
  styleBuiltIn?: string;
  tableNestingLevel?: number;
  search(searchText: string, options: { matchCase: boolean }): OfficeRangeCollection;
}

export interface OfficeParagraphCollection {
  items: OfficeParagraph[];
  load(props?: string): void;
}

export interface WordRequestContext {
  document: {
    body: { paragraphs: OfficeParagraphCollection };
    changeTrackingMode: string;
    load(props: string): void;
  };
  sync(): Promise<unknown>;
}

export interface OfficeApi {
  Office: {
    onReady(callback?: (info: { host: string | null; platform: string | null }) => void): Promise<{
      host: string | null;
      platform: string | null;
    }>;
    context: { requirements: { isSetSupported(name: string, minVersion?: string): boolean } };
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

export function canTrackChanges(api: OfficeApi): boolean {
  try {
    return api.Office.context.requirements.isSetSupported("WordApi", "1.4");
  } catch {
    return false;
  }
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

/** The document body's paragraphs, in order (footnotes, headers and text boxes are not included). */
export function readParagraphs(api: OfficeApi): Promise<WordParagraph[]> {
  return api.Word.run(async (ctx) => {
    const paras = ctx.document.body.paragraphs;
    paras.load("items/text,items/style,items/styleBuiltIn,items/tableNestingLevel");
    await ctx.sync();
    return paras.items.map(toWordParagraph);
  });
}

/* ---------- finding a suggestion again ---------- */

export type ActionResult<T> = ({ ok: true } & T) | { ok: false; message: string };

export const CHANGED_MESSAGE =
  "The document has changed here since the check, so nothing was selected or changed. Check the document again.";
export const NOT_FOUND_MESSAGE =
  "Word could not find this text exactly, so nothing was changed. Check the document again; if this keeps happening, make the change by hand.";
export const APPROXIMATE_APPLY_MESSAGE =
  "This passage is too long for Word to find whole, so the revision can't be applied safely. Make the change by hand.";
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
): Promise<{ ok: true; range: OfficeRange } | { ok: false; message: string }> {
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
  return range ? { ok: true, range } : { ok: false, message: NOT_FOUND_MESSAGE };
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

async function overlapsField(ctx: WordRequestContext, range: OfficeRange, api: OfficeApi): Promise<boolean> {
  if (!canTrackChanges(api) || !range.fields) return false; // fields arrived with WordApi 1.4
  try {
    range.fields.load("items");
    await ctx.sync();
    return range.fields.items.length > 0;
  } catch {
    return false; // a build without the fields API: nothing to protect
  }
}

/**
 * Replace the flagged words with the suggested revision, as a tracked change
 * where Word supports it. The writer's own Track Changes setting is restored
 * afterwards.
 */
export async function applyReplacement(
  api: OfficeApi,
  loc: WordLocation,
  replacement: string,
): Promise<ActionResult<{ tracked: boolean }>> {
  if (!loc.exact) return { ok: false, message: APPROXIMATE_APPLY_MESSAGE };
  const track = canTrackChanges(api);
  try {
    return await api.Word.run(async (ctx) => {
      const found = await findRange(ctx, loc);
      if (!found.ok) return found;
      const range = found.range;
      // Re-read the very range about to be replaced.
      range.load("text");
      await ctx.sync();
      if (range.text !== loc.snippet) return { ok: false as const, message: RANGE_CHANGED_MESSAGE };
      if (await overlapsField(ctx, range, api)) return { ok: false as const, message: FIELD_MESSAGE };

      let prior: string | null = null;
      if (track) {
        ctx.document.load("changeTrackingMode");
        await ctx.sync();
        prior = ctx.document.changeTrackingMode;
        if (prior !== "TrackAll") ctx.document.changeTrackingMode = "TrackAll";
      }
      try {
        range.insertText(replacement, "Replace");
        range.select();
        await ctx.sync();
      } finally {
        if (track && prior !== null && prior !== "TrackAll") {
          ctx.document.changeTrackingMode = prior;
          await ctx.sync();
        }
      }
      return { ok: true as const, tracked: track };
    });
  } catch {
    return { ok: false, message: WORD_FAILED_MESSAGE };
  }
}

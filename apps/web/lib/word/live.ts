/**
 * Underlines in the Word document (S4d R4), the pure part: everything that
 * can be decided without Word, unit-tested in tests/unit/word-live.test.ts.
 *
 * - Colours come from the design tokens (Correction red, Improvement blue,
 *   Convention green, Preference lavender); Word's annotation colours are
 *   a fixed set, so these are names, not values.
 * - Offsets: the live check answers in UTF-16 (`begin`/`end`), which is what
 *   JavaScript strings and Word count in. A range is used only if the
 *   paragraph's text there is exactly the flagged words.
 * - Document-wide findings are never underlines: underlining one word for a
 *   whole-document problem misleads (docs/inline-review-design.md §2).
 */
import type { Category, LiveSuggestion, WordLocation, WordParagraph, WordSuggestion } from "@researchly/contract";
import { CATEGORY_TOKENS } from "@researchly/design-tokens";
import { CATEGORY_ORDER } from "../categories";
import { isDocumentWide, type ScopeMap } from "../scope";
import { isHeadingParagraph } from "./view";

/* ---------- colour and popup ---------- */

/** Word's critique colour schemes (WordApi 1.7). */
export type CritiqueColor = "Red" | "Green" | "Blue" | "Lavender" | "Berry";

/** The annotation colour for a category, from the tokens: never red for anything but a likely error. */
export function annotationColor(category: Category): CritiqueColor {
  return CATEGORY_TOKENS[category].wordAnnotationColor;
}

/**
 * The popup's strings are manifest string resources (WordApi 1.8 takes
 * resource ids, not text): apps/word-addin/manifest.hosted.xml,
 * `<bt:ShortStrings>`. Each id is at most 32 characters (Word for Mac drops
 * a manifest with a longer one, silently).
 */
export const POPUP_RESOURCES = {
  branding: "RL.CritiqueBrand",
  subtitle: "RL.CritiqueSubtitle",
  title: {
    correction: "RL.CritiqueCorrection",
    improvement: "RL.CritiqueImprovement",
    convention: "RL.CritiqueConvention",
    preference: "RL.CritiquePreference",
  } satisfies Record<Category, string>,
} as const;

/** The popup shows at most three revisions. */
export const MAX_POPUP_SUGGESTIONS = 3;

/**
 * The revisions the popup may offer: only where the rule's revision is safe
 * to take without reading the card (`fix_safety` "safe"). A "review" fix is
 * applied from the pane, where the why sits next to it. A removal ("") is
 * never offered in the popup: an empty choice reads as nothing.
 */
export function popupSuggestions(s: { fix_safety: string; replacements?: readonly string[] | null }): string[] {
  if (s.fix_safety !== "safe") return [];
  const out: string[] = [];
  for (const r of s.replacements ?? []) {
    if (r && !out.includes(r)) out.push(r);
    if (out.length === MAX_POPUP_SUGGESTIONS) break;
  }
  return out;
}

/** Preferences are underlined only when "Show preferences" is on (CLAUDE.md #3). */
export function shouldUnderline(category: Category, showPreferences: boolean): boolean {
  return category !== "preference" || showPreferences;
}

/* ---------- paragraphs: keys, headings, what changed ---------- */

/**
 * A paragraph's key: Word's own id where it has one (WordApi 1.6
 * `uniqueLocalId`, braces and all stripped to the contract's id
 * alphabet), otherwise its position.
 */
export function paragraphKey(uniqueLocalId: string | null | undefined, index: number): string {
  const clean = (uniqueLocalId ?? "").replace(/[^A-Za-z0-9._:-]/g, "");
  return clean ? `u${clean}`.slice(0, 64) : `i${index}`;
}

/** A paragraph as read for the live check: its text and style, its key, and the nearest heading above it. */
export interface SnapshotParagraph extends WordParagraph {
  key: string;
  index: number;
  /** The text of the closest heading-styled paragraph above (not itself); "" above the first heading. */
  heading: string;
}

/** Each paragraph's nearest heading above it: walk back to the closest paragraph in a heading style. */
export function nearestHeadings(paragraphs: readonly WordParagraph[]): string[] {
  const out: string[] = [];
  let last = "";
  for (const p of paragraphs) {
    out.push(last);
    if (isHeadingParagraph(p)) last = p.text.trim();
  }
  return out;
}

export function snapshotOf(paragraphs: readonly WordParagraph[], keys: readonly string[]): SnapshotParagraph[] {
  const headings = nearestHeadings(paragraphs);
  return paragraphs.map((p, index) => ({ ...p, key: keys[index] ?? `i${index}`, index, heading: headings[index] ?? "" }));
}

/** Only body prose is checked live: not headings (masked anyway), not table cells, not blank lines. */
export function isLiveCheckable(p: WordParagraph): boolean {
  return p.kind !== "table" && !isHeadingParagraph(p) && p.text.trim().length > 0;
}

/** What a check of this paragraph depends on: its text, its style and its section. */
export function signature(p: Pick<SnapshotParagraph, "text" | "style" | "kind" | "heading">): string {
  return `${p.kind}\u0001${p.style}\u0001${p.heading}\u0001${p.text}`;
}

/** The paragraphs whose text, style or section changed since they were last checked (or never were). */
export function changedParagraphs(snapshot: readonly SnapshotParagraph[], known: ReadonlyMap<string, string>): SnapshotParagraph[] {
  return snapshot.filter((p) => known.get(p.key) !== signature(p));
}

/** Keys held for paragraphs that are no longer in the document. */
export function goneKeys(snapshot: readonly SnapshotParagraph[], held: Iterable<string>): string[] {
  const here = new Set(snapshot.map((p) => p.key));
  return [...held].filter((k) => !here.has(k));
}

/* ---------- offsets ---------- */

function isHigh(c: number) {
  return c >= 0xd800 && c <= 0xdbff;
}
function isLow(c: number) {
  return c >= 0xdc00 && c <= 0xdfff;
}

/** Whether a UTF-16 index falls between two characters (not inside a surrogate pair). */
export function onBoundary(text: string, i: number): boolean {
  if (i <= 0 || i >= text.length) return i === 0 || i === text.length;
  return !(isLow(text.charCodeAt(i)) && isHigh(text.charCodeAt(i - 1)));
}

/** A UTF-16 offset as a code-point offset (Python's indices), or null if it splits a character or is out of range. */
export function utf16ToCodePoint(text: string, i16: number): number | null {
  if (!Number.isInteger(i16) || i16 < 0 || i16 > text.length || !onBoundary(text, i16)) return null;
  let cp = 0;
  for (let i = 0; i < i16; i++) {
    if (!(isLow(text.charCodeAt(i)) && i > 0 && isHigh(text.charCodeAt(i - 1)))) cp++;
  }
  return cp;
}

/** A code-point offset as a UTF-16 offset, or null when out of range. */
export function codePointToUtf16(text: string, cp: number): number | null {
  if (!Number.isInteger(cp) || cp < 0) return null;
  let i16 = 0;
  let n = 0;
  for (const ch of text) {
    if (n === cp) return i16;
    i16 += ch.length;
    n++;
  }
  return n === cp ? i16 : null;
}

/**
 * Word's critique range (`start`, `length`, UTF-16 within the paragraph)
 * for the engine's `begin`/`end`, or null when it cannot be trusted: out of
 * range, empty, splitting a character, or (with `expect`) not reading
 * exactly the flagged words.
 */
export function critiqueRange(text: string, begin: number, end: number, expect?: string): { start: number; length: number } | null {
  if (!Number.isInteger(begin) || !Number.isInteger(end) || begin < 0 || end <= begin || end > text.length) return null;
  if (!onBoundary(text, begin) || !onBoundary(text, end)) return null;
  if (expect !== undefined && text.slice(begin, end) !== expect) return null;
  return { start: begin, length: end - begin };
}

/** Python-style non-overlapping matches, left to right: which one starts at `begin16`, or -1. */
export function occurrenceAt(text: string, needle: string, begin16: number): number {
  if (!needle) return -1;
  let n = 0;
  for (let i = text.indexOf(needle); i >= 0; i = text.indexOf(needle, i + needle.length)) {
    if (i === begin16) return n;
    if (i > begin16) return -1;
    n++;
  }
  return -1;
}

/**
 * How the pane finds a live suggestion again (the same WordLocation as the
 * full check's): code-point offsets, the flagged words as the snippet, and
 * which copy of them it is. Null when the reply does not fit the text sent.
 */
export function liveLocation(paragraphText: string, paragraph: number, s: Pick<LiveSuggestion, "begin" | "end" | "text">): WordLocation | null {
  if (!critiqueRange(paragraphText, s.begin, s.end, s.text)) return null;
  const start = utf16ToCodePoint(paragraphText, s.begin);
  const end = utf16ToCodePoint(paragraphText, s.end);
  if (start === null || end === null) return null;
  const occurrence = occurrenceAt(paragraphText, s.text, s.begin);
  // An overlapping repeat (Word's search cannot reach it whole): the start is found, and the card says it is approximate.
  return {
    paragraph,
    start,
    end,
    snippet: s.text,
    occurrence: Math.max(occurrence, 0),
    exact: occurrence >= 0,
    begin16: s.begin,
    end16: s.end,
  };
}

/** A live suggestion as a pane card (the shape the full check's cards have), or null when it does not fit the text. */
export function liveToWordSuggestion(s: LiveSuggestion, paragraph: number, paragraphText: string): WordSuggestion | null {
  const location = liveLocation(paragraphText, paragraph, s);
  if (!location) return null;
  return {
    id: s.id,
    rule_id: s.rule_id,
    rule_name: s.rule_name,
    category: s.category,
    critical: s.critical,
    tier: s.tier,
    section: s.section,
    message: s.message,
    plain: s.plain ?? "",
    why: s.why,
    source: s.source,
    learn_ref: s.learn_ref ?? null,
    fix_safety: s.fix_safety,
    confidence: 1,
    replacement: s.replacements && s.replacements.length > 0 ? s.replacements[0]! : null,
    text: s.text,
    span: { start: location.start, end: location.end, line: 1, col: location.start + 1 },
    begin16: s.begin,
    end16: s.end,
    location,
  };
}

/** A full-check suggestion's UTF-16 range in its paragraph: `begin16`/`end16` when the engine sent them, else converted. */
export function fullRange(s: Pick<WordSuggestion, "location" | "text">, paragraphText: string): { begin: number; end: number } | null {
  const loc = s.location;
  const begin = loc.begin16 ?? codePointToUtf16(paragraphText, loc.start);
  const end = loc.end16 ?? codePointToUtf16(paragraphText, loc.end);
  if (begin === null || end === null || begin === undefined || end === undefined) return null;
  return critiqueRange(paragraphText, begin, end, s.text) ? { begin, end } : null;
}

/* ---------- which findings become underlines ---------- */

/** One underline to draw: a suggestion's range, its category and the popup's revisions. */
export interface Underline {
  id: string;
  category: Category;
  begin: number;
  end: number;
  suggestions: string[];
}

/**
 * Underlines never overlap: where two findings cover the same words, the
 * more serious category wins (Correction first), then the shorter range.
 * The other stays a card in the pane, without "In the text".
 */
export function pickUnderlines(items: readonly Underline[]): Underline[] {
  const rank = (u: Underline) => CATEGORY_ORDER.indexOf(u.category);
  const ordered = [...items].sort((a, b) => rank(a) - rank(b) || a.end - a.begin - (b.end - b.begin) || a.begin - b.begin);
  const kept: Underline[] = [];
  for (const u of ordered) {
    if (kept.every((k) => u.end <= k.begin || u.begin >= k.end)) kept.push(u);
  }
  return kept.sort((a, b) => a.begin - b.begin);
}

/** A suggestion as an underline in its paragraph's text, or null (document-wide, hidden preference, or a range that does not fit). */
export function underlineFor(
  s: WordSuggestion,
  paragraphText: string,
  opts: { showPreferences: boolean; scopes: ScopeMap | null },
): Underline | null {
  if (isDocumentWide(s.rule_id, opts.scopes) || !shouldUnderline(s.category, opts.showPreferences)) return null;
  const r = fullRange(s, paragraphText);
  if (!r) return null;
  return {
    id: s.id,
    category: s.category,
    begin: r.begin,
    end: r.end,
    suggestions: popupSuggestions({ fix_safety: s.fix_safety, replacements: s.replacement ? [s.replacement] : [] }),
  };
}

/** Underlines for one paragraph's cards: in range, sentence-scope, shown, not dismissed, never overlapping. */
export function paragraphUnderlines(
  cards: readonly WordSuggestion[],
  paragraphText: string,
  opts: { showPreferences: boolean; scopes: ScopeMap | null; dismissed?: (s: WordSuggestion) => boolean },
): Underline[] {
  const list: Underline[] = [];
  for (const s of cards) {
    if (opts.dismissed?.(s)) continue;
    const u = underlineFor(s, paragraphText, opts);
    if (u) list.push(u);
  }
  return pickUnderlines(list);
}

/* ---------- the pane's list: the full check, with live paragraphs swapped in ---------- */

/** One paragraph's live result, as cards: what the pane shows for it instead of the full check's sentence-level cards. */
export interface LiveEntry {
  key: string;
  /** Where the paragraph was when it was read. */
  index: number;
  /** The text that was checked (the cards' offsets refer to it). */
  text: string;
  cards: WordSuggestion[];
}

/**
 * The cards on show: the full check's, except the sentence-level ones of a
 * paragraph checked live since (that paragraph's live cards stand in), and
 * every live paragraph's cards. Document-wide findings always come from
 * the full check. In document order.
 */
export function mergeCards(
  full: readonly WordSuggestion[] | null,
  fullKeys: readonly string[],
  live: ReadonlyMap<string, LiveEntry>,
  scopes: ScopeMap | null,
): WordSuggestion[] {
  const out: WordSuggestion[] = [];
  for (const s of full ?? []) {
    const key = fullKeys[s.location.paragraph];
    if (isDocumentWide(s.rule_id, scopes) || key === undefined || !live.has(key)) out.push(s);
  }
  for (const e of live.values()) out.push(...e.cards);
  return out.sort(
    (a, b) =>
      a.location.paragraph - b.location.paragraph ||
      a.location.start - b.location.start ||
      CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category) ||
      (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
}

/** "Not an issue here" outlives a re-check of the same words: paragraph, rule and flagged text (memory only). */
export function dismissalKey(paragraphKey: string, s: Pick<WordSuggestion, "rule_id" | "text">): string {
  return `${paragraphKey}\u0001${s.rule_id}\u0001${s.text}`;
}

/**
 * Whether Word has already made this revision (a popup's Accept may apply
 * it itself): the paragraph reads as before with the flagged range replaced.
 */
export function appliedInPlace(before: string, now: string, begin16: number, end16: number, replacement: string): boolean {
  return now === before.slice(0, begin16) + replacement + before.slice(end16);
}

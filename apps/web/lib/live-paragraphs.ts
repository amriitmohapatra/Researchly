/**
 * Underlines while writing (S4d R5): the pure part. Everything here is
 * synchronous, free of the DOM and unit-tested (tests/unit/live-paragraphs.test.ts).
 *
 * - Split the editor's text into paragraphs the way the engine reads plain
 *   text and Markdown (packages/core/researchly/document.py): a blank line
 *   ends a paragraph; a heading line stands alone (Markdown `#` lines; in
 *   plain text a short capitalised line that names a section, such as
 *   "Methods"); fenced code and front matter are not prose.
 * - Give each paragraph the heading that decides its section, resolved as
 *   `resolve_sections` does (a "Priors" subsection under "Methods" is
 *   Methods), so a live check is section-aware without the whole document.
 * - Key each paragraph by a hash of its heading and its text: results are
 *   cached by key, so an unchanged paragraph is never sent again and an
 *   undo brings its underlines straight back.
 * - Turn a paragraph's suggestions (UTF-16 ranges) into the marks the
 *   editor's mirror draws, and carry underlines across an edit while the
 *   words they sit on are unchanged.
 *
 * Offsets are UTF-16 code units throughout: JavaScript string indices, the
 * unit `/v1/check-paragraphs` answers in.
 */
import {
  MAX_LIVE_CHARS,
  MAX_LIVE_HEADING_CHARS,
  MAX_LIVE_PARAGRAPHS,
  type Category,
  type Format,
  type LiveSuggestion,
  type Suggestion,
} from "@researchly/contract";
import { buildOffsetMap, segment, type ResolvedSpan, type Segment } from "./segments";

/** The formats whose text the live check can read as it is (LaTeX markup it cannot: press Check). */
export type LiveFormat = "plain" | "markdown";

export function isLiveFormat(format: Format): format is LiveFormat {
  return format === "plain" || format === "markdown";
}

/* ---------- sections, ported from document.py ---------- */

const SECTION_PATTERNS: readonly (readonly [RegExp, string])[] = [
  [/^\W*(references|bibliography|literature cited|works cited|reference list|cited literature)\W*$/, "references"],
  [/appendix|appendices|supplement/, "appendix"],
  [/abstract|summary\b/, "abstract"],
  [/introduction|background/, "introduction"],
  [/method|material|model|data\b|analys[ie]s|estimation|inference|statistic|design|setting|participants/, "methods"],
  [/result|finding/, "results"],
  [/limitation/, "limitations"],
  [/discussion/, "discussion"],
  [/conclusion/, "conclusion"],
];

/** document.py `classify_heading`. */
export function classifyHeading(text: string): string {
  const low = text.toLowerCase();
  for (const [pattern, name] of SECTION_PATTERNS) if (pattern.test(low)) return name;
  return "other";
}

const SECTION_NAME_WORDS = new Set(
  `abstract summary introduction background literature review aims aim
   objectives methods method methodology materials material data
   statistical statistics analysis analyses experimental procedures
   results result findings discussion general conclusion conclusions
   concluding remarks limitations strengths appendix appendices
   supplementary supplemental information references bibliography`.split(/\s+/),
);
const SECTION_NAME_FILLER = new Set(["and", "of", "the", "a", "an", "s"]);
const NUMBERING = /^\s*(?:(?:chapter|part|section|appendix)\s+)?(?:[0-9]+|[ivxlc]+|[a-z])(?:[.:][0-9]+)*[.:)]?\s+/i;

/** document.py `is_section_name`: a heading that is just a section name, numbered or not. */
export function isSectionName(title: string): boolean {
  const words = (title.toLowerCase().replace(NUMBERING, "").match(/[a-z]+/g) ?? []).filter((w) => !SECTION_NAME_FILLER.has(w));
  return words.length > 0 && words.every((w) => SECTION_NAME_WORDS.has(w));
}

export interface HeadingLine {
  /** UTF-16 offset of the line in the text. */
  start: number;
  end: number;
  /** The heading's words (no `#` marks). */
  text: string;
  /** Markdown depth (1–6); null for a plain-text heading, which stands alone. */
  level: number | null;
  /** The section it resolves to, as the engine would resolve it. */
  section: string;
  /**
   * The heading text to send with the paragraphs under it: its own words
   * when they name its section, else those of the heading it inherits the
   * section from, so the engine (which sees one heading) lands on the same
   * section as the full check.
   */
  sendAs: string;
}

/** document.py `resolve_sections`: a nested heading inherits its parent's section unless it names its own. */
export function resolveSections(headings: HeadingLine[]): void {
  type Open = { h: HeadingLine; authoritative: boolean };
  let stack: Open[] = [];
  for (const h of headings) {
    const own = classifyHeading(h.text);
    const named = isSectionName(h.text);
    if (h.level === null) {
      stack = [];
      h.section = own;
      h.sendAs = h.text;
      continue;
    }
    while (stack.length && (stack[stack.length - 1]!.h.level ?? 0) >= h.level) stack.pop();
    const parent = stack.length ? stack[stack.length - 1]! : null;
    let authoritative: boolean;
    if (parent === null || parent.h.section === "other") {
      h.section = own;
      h.sendAs = h.text;
      authoritative = named;
    } else if (own === "other") {
      h.section = parent.h.section;
      h.sendAs = parent.h.sendAs;
      authoritative = parent.authoritative;
    } else if (parent.authoritative && !named) {
      h.section = parent.h.section;
      h.sendAs = parent.h.sendAs;
      authoritative = true;
    } else {
      h.section = own;
      h.sendAs = h.text;
      authoritative = named;
    }
    stack.push({ h, authoritative });
  }
}

/* ---------- splitting ---------- */

export interface LiveParagraph {
  /** Position among the paragraphs (0-based). */
  index: number;
  /** UTF-16 offsets of the paragraph in the editor's text. */
  start: number;
  end: number;
  text: string;
  /** The heading text sent with it (see HeadingLine.sendAs); "" before any heading. */
  heading: string;
  /** Hash of heading and text: the cache key and, prefixed, the id sent to the engine. */
  key: string;
}

export interface LiveDocument {
  paragraphs: LiveParagraph[];
  headings: HeadingLine[];
}

const PLAIN_HEADING = /^([A-Z][A-Za-z &-]{2,60})\s*$/;
const MD_HEADING = /^(#{1,6})[ \t]+([^\n{]+)/;
const MD_FENCE = /^(```|~~~)/;

/** A plain-text heading line, as `_detect_plain_headings` finds it; null otherwise. */
function plainHeading(line: string): string | null {
  const m = PLAIN_HEADING.exec(line);
  if (!m) return null;
  const title = m[1]!.trim();
  if (title.includes("   ")) return null; // aligned columns: a table row
  return classifyHeading(title) === "other" ? null : title;
}

/**
 * The editor's text as paragraphs, each under the heading that decides its
 * section. Paragraph text keeps its inner line breaks; offsets are the
 * text's own (UTF-16).
 */
export function splitParagraphs(
  text: string,
  format: LiveFormat,
  keyOf: (heading: string, text: string) => string = paragraphKey,
): LiveDocument {
  const headings: HeadingLine[] = [];
  type Block = { start: number; end: number; headingIndex: number };
  const blocks: Block[] = [];
  let open: Block | null = null;
  let fence: string | null = null;
  let pos = 0;
  const len = text.length;

  // Markdown front matter at the very top is metadata, not prose.
  if (format === "markdown") {
    const fm = /^---\n[\s\S]*?\n(?:---|\.\.\.)[ \t]*(?:\n|$)/.exec(text);
    if (fm) pos = fm[0].length;
  }

  while (pos <= len) {
    let nl = text.indexOf("\n", pos);
    if (nl === -1) nl = len;
    const line = text.slice(pos, nl);
    const lineEnd = line.endsWith("\r") ? nl - 1 : nl;
    const body = line.endsWith("\r") ? line.slice(0, -1) : line;
    let heading: string | null = null;
    let level: number | null = null;
    let prose = body.trim().length > 0;

    if (format === "markdown") {
      const f = MD_FENCE.exec(body);
      if (fence !== null) {
        prose = false;
        if (f && f[1] === fence) fence = null;
      } else if (f) {
        fence = f[1]!;
        prose = false;
      } else if (/^:{3,}/.test(body)) {
        prose = false; // a Quarto div fence: markers only
      } else {
        const m = MD_HEADING.exec(body);
        if (m) {
          heading = m[2]!.trim() || null;
          level = m[1]!.length;
          prose = false;
        }
      }
    } else if (prose) {
      heading = plainHeading(body);
      if (heading !== null) prose = false;
    }

    if (heading !== null) {
      headings.push({ start: pos, end: lineEnd, text: heading, level, section: "other", sendAs: heading });
    }
    if (prose) {
      if (open) open.end = lineEnd;
      else open = { start: pos, end: lineEnd, headingIndex: headings.length - 1 };
    } else if (open) {
      blocks.push(open);
      open = null;
    }
    if (nl >= len) break;
    pos = nl + 1;
  }
  if (open) blocks.push(open);

  resolveSections(headings);
  const paragraphs = blocks.map((b, index): LiveParagraph => {
    const paraText = text.slice(b.start, b.end);
    const heading = b.headingIndex >= 0 ? headings[b.headingIndex]!.sendAs.slice(0, MAX_LIVE_HEADING_CHARS) : "";
    return { index, start: b.start, end: b.end, text: paraText, heading, key: keyOf(heading, paraText) };
  });
  return { paragraphs, headings };
}

/* ---------- keys ---------- */

/** Two 32-bit FNV-1a passes with different seeds, over heading, a separator and text. */
export function paragraphKey(heading: string, text: string): string {
  let a = 0x811c9dc5;
  let b = 0x01000193 ^ 0x5bd1e995;
  const feed = (s: string) => {
    for (let i = 0; i < s.length; i++) {
      const c = s.charCodeAt(i);
      a = Math.imul(a ^ c, 0x01000193);
      b = Math.imul(b ^ c, 0x0100019b);
    }
  };
  feed(heading);
  feed("\u0001");
  feed(text);
  return `${(a >>> 0).toString(36)}${(b >>> 0).toString(36)}${text.length.toString(36)}`;
}

/** The id a paragraph is sent with: letters and digits only, within the contract's 64 characters. */
export function paragraphId(key: string): string {
  return `k${key}`;
}

/* ---------- what is sent ---------- */

/**
 * Markdown formatting the engine's plain-paragraph reading would otherwise
 * take for words: emphasis marks, link brackets and targets, images, HTML
 * tags and comments, citation groups (`[@key]`) and bare `@keys`. Each is
 * replaced by spaces, so every offset in the reply still points at the
 * writer's own characters. Inline maths and `code` are left to the engine,
 * which reads them as it does in plain text.
 */
export function maskMarkdownInline(text: string): string {
  const spans: [number, number][] = [];
  const all = (re: RegExp) => {
    for (const m of text.matchAll(re)) spans.push([m.index, m.index + m[0].length]);
  };
  all(/!\[[^\]\n]*\]\([^)\n]*\)/g);
  all(/\[[^\]\n]*@[^\]\n]*\]/g);
  all(/(?<![\w.])@[\w:.-]+/g);
  for (const m of text.matchAll(/\[([^\]\n]+)\]\(([^)\n]*)\)/g)) {
    const at = m.index;
    spans.push([at, at + 1]); // '['
    spans.push([at + 1 + m[1]!.length, at + m[0].length]); // '](url)'
  }
  all(/<!--[\s\S]*?-->/g);
  all(/<\/?[a-zA-Z][^>\n]*>/g);
  all(/\*{1,3}/g);
  all(/(?<!\w)_{1,3}(?=\w)|(?<=\w)_{1,3}(?!\w)/g);
  if (spans.length === 0) return text;
  const chars = text.split("");
  for (const [a, b] of spans) {
    for (let i = a; i < b && i < chars.length; i++) if (chars[i] !== "\n") chars[i] = " ";
  }
  return chars.join("");
}

/** The text a paragraph is checked as: as written, or with Markdown formatting blanked. */
export function textToSend(p: LiveParagraph, format: LiveFormat): string {
  return format === "markdown" ? maskMarkdownInline(p.text) : p.text;
}

/** Whether a paragraph can go in a live request at all (a very long one cannot: press Check). */
export function canSend(p: LiveParagraph): boolean {
  return p.text.trim().length > 0 && p.text.length <= MAX_LIVE_CHARS;
}

/**
 * The next request's paragraphs: those still to check, nearest the caret
 * first, one per key, within the contract's limits (50 paragraphs, 20,000
 * characters together).
 */
export function nextBatch(todo: readonly LiveParagraph[], caret: number): LiveParagraph[] {
  const near = (p: LiveParagraph) => (caret < p.start ? p.start - caret : caret > p.end ? caret - p.end : 0);
  const ordered = [...todo].sort((x, y) => near(x) - near(y) || x.start - y.start);
  const out: LiveParagraph[] = [];
  const keys = new Set<string>();
  let chars = 0;
  for (const p of ordered) {
    if (keys.has(p.key) || !canSend(p)) continue;
    if (out.length >= MAX_LIVE_PARAGRAPHS || chars + p.text.length > MAX_LIVE_CHARS) break;
    keys.add(p.key);
    chars += p.text.length;
    out.push(p);
  }
  return out;
}

/* ---------- what is drawn ---------- */

/** One underline: what the mirror, the teaser and the card need. */
export interface LiveItem {
  id: string;
  rule_id: string;
  rule_name: string;
  category: Category;
  /** UTF-16 offsets within the paragraph. */
  begin: number;
  end: number;
  /** The flagged words, checked before a revision is applied. */
  text: string;
  message: string;
  plain: string;
  why: string;
  source: string;
  learn_ref: string | null;
  section: string;
  tier: string;
  fix_safety: Suggestion["fix_safety"];
  /** Concrete revisions, best first; empty when there is none. */
  replacements: string[];
}

const CATEGORY_SET: ReadonlySet<string> = new Set(["correction", "improvement", "convention", "preference"]);

/** A live suggestion as drawn; null when it cannot be placed in its paragraph. */
export function fromLive(s: LiveSuggestion, paragraph: string): LiveItem | null {
  if (!CATEGORY_SET.has(s.category)) return null;
  const begin = Math.max(0, Math.min(s.begin, s.end));
  const end = Math.max(s.begin, s.end);
  if (end > paragraph.length) return null;
  return {
    id: s.id,
    rule_id: s.rule_id,
    rule_name: s.rule_name,
    category: s.category,
    begin,
    end,
    // The writer's own words (a Markdown paragraph is sent with its formatting blanked).
    text: paragraph.slice(begin, end),
    message: s.message,
    plain: s.plain ?? "",
    why: s.why ?? "",
    source: s.source ?? "",
    learn_ref: s.learn_ref ?? null,
    section: s.section ?? "",
    tier: s.tier ?? "",
    fix_safety: s.fix_safety,
    replacements: Array.isArray(s.replacements) ? s.replacements.filter((r) => typeof r === "string") : [],
  };
}

/** A live item in the shape SuggestionCard reads (offsets relative to the paragraph). */
export function asSuggestion(item: LiveItem, idPrefix = ""): Suggestion {
  return {
    id: `${idPrefix}${item.id}`,
    rule_id: item.rule_id,
    rule_name: item.rule_name,
    category: item.category,
    confidence: 1,
    critical: item.category === "correction",
    fix_safety: item.fix_safety,
    learn_ref: item.learn_ref,
    message: item.message,
    plain: item.plain,
    why: item.why,
    source: item.source,
    section: item.section,
    tier: item.tier,
    text: item.text,
    replacement: item.replacements.length ? item.replacements[0]! : null,
    span: { start: item.begin, end: item.end, line: 0, col: 0 },
    begin16: item.begin,
    end16: item.end,
  };
}

/** Which items a writer sees: Preferences only when they asked for them, none they set aside. */
export function visibleItems(items: readonly LiveItem[], showPreferences: boolean, dismissed: ReadonlySet<string>): LiveItem[] {
  return items.filter((i) => (showPreferences || i.category !== "preference") && !dismissed.has(i.id));
}

function isHigh(c: number) {
  return c >= 0xd800 && c <= 0xdbff;
}
function isLow(c: number) {
  return c >= 0xdc00 && c <= 0xdfff;
}

/** Never split a surrogate pair: an offset inside one moves to the pair's start. */
export function snapUtf16(text: string, at: number): number {
  const i = Math.max(0, Math.min(at, text.length));
  if (i > 0 && i < text.length && isLow(text.charCodeAt(i)) && isHigh(text.charCodeAt(i - 1))) return i - 1;
  return i;
}

/**
 * A paragraph cut into the mirror's runs: plain text, and underlined
 * stretches carrying every item over them (overlaps render once, the most
 * important category styling the line). Concatenating the runs' text gives
 * the paragraph back exactly.
 */
export function paragraphMarks(text: string, items: readonly LiveItem[]): Segment[] {
  const spans: ResolvedSpan[] = items.map((i) => {
    const start = snapUtf16(text, i.begin);
    const end = Math.max(start, snapUtf16(text, i.end));
    return { id: i.id, category: i.category, start, end, inRange: i.end <= text.length };
  });
  return segment(text, spans);
}

/* ---------- carrying underlines across an edit ---------- */

/**
 * The underlines of `before` that still sit on unchanged words of `after`:
 * those wholly before the edit keep their place, those wholly after it move
 * with it, and any the edit touched are dropped (the next reply decides).
 * Each kept item must still cover the same words.
 */
export function carryItems(items: readonly LiveItem[], before: string, after: string): LiveItem[] {
  if (items.length === 0) return [];
  let p = 0;
  const max = Math.min(before.length, after.length);
  while (p < max && before.charCodeAt(p) === after.charCodeAt(p)) p++;
  let s = 0;
  while (s < max - p && before.charCodeAt(before.length - 1 - s) === after.charCodeAt(after.length - 1 - s)) s++;
  const oldEditEnd = before.length - s;
  const delta = after.length - before.length;
  const out: LiveItem[] = [];
  for (const i of items) {
    let moved: LiveItem | null = null;
    if (i.end < p || (i.end === p && i.begin < i.end)) moved = i;
    else if (i.begin > oldEditEnd || (i.begin === oldEditEnd && i.begin < i.end)) moved = { ...i, begin: i.begin + delta, end: i.end + delta };
    if (moved && after.slice(moved.begin, moved.end) === before.slice(i.begin, i.end)) out.push(moved);
  }
  return out;
}

/* ---------- a full check's suggestions as underlines ---------- */

/**
 * The full check's sentence-level suggestions, by paragraph key, so the
 * underlines and the results agree after Check (document-wide findings are
 * never underlines). Every paragraph of the checked text gets an entry,
 * empty when nothing was found, so none is sent again until it changes.
 */
export function itemsFromFullCheck(
  text: string,
  format: LiveFormat,
  suggestions: readonly Suggestion[],
  isDocumentWide: (ruleId: string) => boolean,
): Map<string, LiveItem[]> {
  const doc = splitParagraphs(text, format);
  const map = buildOffsetMap(text);
  const out = new Map<string, LiveItem[]>();
  for (const p of doc.paragraphs) if (!out.has(p.key)) out.set(p.key, []);
  const starts = doc.paragraphs.map((p) => p.start);
  for (const s of suggestions) {
    if (isDocumentWide(s.rule_id) || !CATEGORY_SET.has(s.category)) continue;
    const a = typeof s.begin16 === "number" ? s.begin16 : map.toUtf16(s.span.start);
    const b = typeof s.end16 === "number" ? s.end16 : map.toUtf16(s.span.end);
    // The paragraph holding the start: the last one starting at or before it.
    let lo = 0;
    let hi = starts.length - 1;
    let at = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (starts[mid]! <= a) {
        at = mid;
        lo = mid + 1;
      } else hi = mid - 1;
    }
    const p = at >= 0 ? doc.paragraphs[at]! : null;
    if (!p || b > p.end || a < p.start) continue; // on a heading, or across paragraphs
    const list = out.get(p.key)!;
    if (list.some((x) => x.id === s.id)) continue;
    list.push({
      id: s.id,
      rule_id: s.rule_id,
      rule_name: s.rule_name,
      category: s.category,
      begin: a - p.start,
      end: b - p.start,
      text: text.slice(a, b),
      message: s.message,
      plain: s.plain ?? "",
      why: s.why ?? "",
      source: s.source ?? "",
      learn_ref: s.learn_ref ?? null,
      section: s.section ?? "",
      tier: s.tier ?? "",
      fix_safety: s.fix_safety,
      replacements: s.replacement !== null && s.replacement !== undefined ? [s.replacement] : [],
    });
  }
  return out;
}

/* ---------- reading out an underline ---------- */

/** The item under a caret (or at it, at either edge), the most important first. */
export function itemAt(items: readonly LiveItem[], offset: number): LiveItem | null {
  let best: LiveItem | null = null;
  const order: readonly Category[] = ["correction", "improvement", "convention", "preference"];
  for (const i of items) {
    if (offset < i.begin || offset > i.end) continue;
    if (!best || order.indexOf(i.category) < order.indexOf(best.category) || (i.category === best.category && i.end - i.begin < best.end - best.begin)) {
      best = i;
    }
  }
  return best;
}

/** One line about an underline, for a list or a screen reader: "Correction: Repeated word (“the the”)". */
export function itemSummary(item: LiveItem, label: string): string {
  const words = item.text.replace(/\s+/g, " ").trim();
  const quoted = words ? ` (“${words.length > 40 ? `${words.slice(0, 39)}…` : words}”)` : "";
  return `${label}: ${item.message}${quoted}`;
}

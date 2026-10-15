/**
 * One question about a word used again and again (Codex review #10): the
 * engine sends one suggestion with `occurrences`, every place the word
 * appears, instead of a card per use. Pure helpers, unit-tested in
 * tests/unit/occurrences.test.tsx.
 */
import type { Suggestion } from "@researchly/contract";

/** Highlight ids for the other places carry this suffix and their number. */
const PLACE_MARK = "~at";

export function placeId(suggestionId: string, index: number): string {
  return `${suggestionId}${PLACE_MARK}${index}`;
}

/** The suggestion a place's highlight belongs to, or the id itself. */
export function placeBase(id: string): string {
  const i = id.lastIndexOf(PLACE_MARK);
  return i > 0 && /^\d+$/.test(id.slice(i + PLACE_MARK.length)) ? id.slice(0, i) : id;
}

/** How many places a grouped suggestion covers; 0 for an ordinary one. */
export function placeCount(s: Pick<Suggestion, "occurrences">): number {
  const n = s.occurrences?.length ?? 0;
  return n > 1 ? n : 0;
}

/** Is this place the suggestion's own span (its highlight is the card's)? */
function isOwn(s: Suggestion, start: number, end: number): boolean {
  return start === s.span.start && end === s.span.end;
}

/**
 * The highlight id for place `index`: the card's own for its own span, a
 * place id for the others. "Show where" focuses this mark.
 */
export function placeMark(s: Suggestion, index: number): string {
  const o = s.occurrences?.[index];
  return o && !isOwn(s, o.start, o.end) ? placeId(s.id, index) : s.id;
}

/**
 * The other places as stand-in suggestions, for resolveSpans(): each is
 * underlined like the card, so every use the count speaks of is visible in
 * the text, and choosing one leads back to the card.
 */
export function placeHighlights(s: Suggestion): Suggestion[] {
  if (placeCount(s) === 0) return [];
  const out: Suggestion[] = [];
  s.occurrences!.forEach((o, i) => {
    if (!(o.end > o.start) || isOwn(s, o.start, o.end)) return;
    out.push({
      ...s,
      id: placeId(s.id, i),
      span: { start: o.start, end: o.end, line: o.line, col: o.col },
      occurrences: null,
    });
  });
  return out;
}

const fmt = new Intl.NumberFormat("en-GB");

/** "Place 2 of 5": where "Show where" is, for the polite live region. */
export function placeLine(index: number, count: number): string {
  return `Place ${fmt.format(index + 1)} of ${fmt.format(count)}`;
}

/**
 * The place one step on, held at either end as the revision queue's
 * Previous and Next are (the button at an end says it is unavailable).
 */
export function stepPlace(index: number | null, count: number, step: 1 | -1): number {
  if (count <= 0) return 0;
  if (index === null) return 0;
  return Math.min(count - 1, Math.max(0, index + step));
}

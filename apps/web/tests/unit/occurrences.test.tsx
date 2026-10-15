import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { Suggestion, WordSuggestion } from "@researchly/contract";
import { SIGNED_OUT_DICTIONARY_NOTE, SuggestionCard } from "@/components/SuggestionCard";
import { WordCard } from "@/components/word/WordCard";
import { DocumentView } from "@/components/DocumentView";
import { PlacesNav } from "@/components/PlacesNav";
import { resolveSpans, segment } from "@/lib/segments";
import { placeBase, placeCount, placeHighlights, placeId, placeLine, placeMark, stepPlace } from "@/lib/occurrences";
import { sugg } from "./helpers";

// Synthetic: a coined term used three times (Codex review #10).
const TEXT = "We fitted numpyro models. The numpyro sampler ran. Then numpyro stopped.";
const at = (n: number) => {
  let i = -1;
  for (let k = 0; k <= n; k++) i = TEXT.indexOf("numpyro", i + 1);
  return i;
};
const OCC = [0, 1, 2].map((n) => ({ start: at(n), end: at(n) + 7, line: 1, col: at(n) + 1 }));
const MESSAGE =
  "‘numpyro’ appears 3 times and isn’t in the dictionary. If it’s a term, add it to your dictionary; otherwise check its spelling.";

function question(extra: Partial<Suggestion> = {}): Suggestion {
  return sugg("q1", OCC[0]!.start, OCC[0]!.end, "convention", {
    rule_id: "S003",
    rule_name: "repeated-unknown-word",
    tier: "spelling",
    text: "numpyro",
    message: MESSAGE,
    occurrences: OCC,
    ...extra,
  });
}

const cardProps = { active: false, placeable: true, onShowInText: () => {} };

describe("the places of a grouped question", () => {
  it("counts only a suggestion about more than one place", () => {
    expect(placeCount(question())).toBe(3);
    expect(placeCount(question({ occurrences: null }))).toBe(0);
    expect(placeCount(question({ occurrences: [OCC[0]!] }))).toBe(0);
  });

  it("underlines every other place, each leading back to the card", () => {
    const stand = placeHighlights(question());
    expect(stand.map((s) => s.id)).toEqual([placeId("q1", 1), placeId("q1", 2)]);
    expect(stand.map((s) => placeBase(s.id))).toEqual(["q1", "q1"]);
    expect(placeBase("q1")).toBe("q1");
    expect(placeBase("q1~cell")).toBe("q1~cell");
    const resolved = resolveSpans(TEXT, stand);
    expect(resolved.map((r) => TEXT.slice(r.start, r.end))).toEqual(["numpyro", "numpyro"]);
    expect(placeHighlights(question({ occurrences: null }))).toEqual([]);
  });

  it("points Show where at the card's own mark for its own place", () => {
    expect(placeMark(question(), 0)).toBe("q1");
    expect(placeMark(question(), 2)).toBe(placeId("q1", 2));
  });

  it("steps like the revision queue: held at either end", () => {
    expect(stepPlace(null, 3, 1)).toBe(0);
    expect(stepPlace(0, 3, -1)).toBe(0);
    expect(stepPlace(0, 3, 1)).toBe(1);
    expect(stepPlace(2, 3, 1)).toBe(2);
    expect(placeLine(1, 3)).toBe("Place 2 of 3");
  });

  it("lights every place when its card is active", () => {
    const q = question();
    const resolved = resolveSpans(TEXT, [q, ...placeHighlights(q)]);
    const html = renderToStaticMarkup(<DocumentView segments={segment(TEXT, resolved)} activeId="q1" onSelect={() => {}} />);
    expect(html.match(/class="hl hl-convention is-active"/g)?.length).toBe(3);
  });
});

describe("the grouped question on the website card", () => {
  it("offers Show where instead of Show in text, and no revision", () => {
    const html = renderToStaticMarkup(<SuggestionCard suggestion={question()} {...cardProps} onShowPlace={() => {}} />);
    expect(html).toContain('data-testid="show-where"');
    expect(html).toContain("Places ‘numpyro’ appears");
    expect(html).not.toContain("Show in text");
    expect(html).not.toContain("Suggested revision");
    expect(html).toContain(MESSAGE);
    expect(html.replace(/<[^>]+>/g, " ")).not.toMatch(/S003|S001/); // no rule code in what a writer reads
  });

  it("offers Add to dictionary when signed in", () => {
    const actions = { onMute: () => {}, onAddWord: () => {}, busy: false };
    const html = renderToStaticMarkup(
      <SuggestionCard suggestion={question()} {...cardProps} onShowPlace={() => {}} actions={actions} />,
    );
    expect(html).toContain('data-testid="add-word"');
    expect(html).toContain("numpyro</q> to dictionary");
    expect(html).not.toContain(SIGNED_OUT_DICTIONARY_NOTE);
  });

  it("says where a dictionary is kept when signed out, and only on the question", () => {
    const html = renderToStaticMarkup(
      <SuggestionCard suggestion={question()} {...cardProps} onShowPlace={() => {}} dictionaryNote={SIGNED_OUT_DICTIONARY_NOTE} />,
    );
    expect(html).toContain('data-testid="dictionary-note"');
    const typo = sugg("t1", 0, 2, "correction", { rule_id: "S001", tier: "spelling", text: "We", occurrences: null });
    const plain = renderToStaticMarkup(<SuggestionCard suggestion={typo} {...cardProps} dictionaryNote={SIGNED_OUT_DICTIONARY_NOTE} />);
    expect(plain).not.toContain("dictionary-note");
    expect(plain).toContain("Show in text");
  });

  it("keeps the copy's typography: curly apostrophes, no em dashes", () => {
    expect(SIGNED_OUT_DICTIONARY_NOTE).not.toMatch(/['—]/);
    const nav = renderToStaticMarkup(<PlacesNav count={3} at={1} onGo={() => {}} word="numpyro" />);
    expect(nav).not.toMatch(/—/);
    expect(nav).toContain("Place 2 of 3");
    expect(nav).toMatch(/aria-label="Previous place"/);
  });

  it("marks Previous unavailable on the first place and Next on the last", () => {
    const first = renderToStaticMarkup(<PlacesNav count={3} at={0} onGo={() => {}} word="w" />);
    expect(first).toMatch(/aria-disabled="true"[^>]*data-testid="place-prev"/);
    expect(first).not.toMatch(/aria-disabled="true"[^>]*data-testid="place-next"/);
    const last = renderToStaticMarkup(<PlacesNav count={3} at={2} onGo={() => {}} word="w" />);
    expect(last).toMatch(/aria-disabled="true"[^>]*data-testid="place-next"/);
    const before = renderToStaticMarkup(<PlacesNav count={3} at={null} onGo={() => {}} word="w" />);
    expect(before).not.toContain("place-prev");
  });
});

describe("the grouped question on the Word card", () => {
  const loc = (n: number) => ({ paragraph: n === 2 ? 3 : 1, start: 0, end: 7, snippet: "numpyro", occurrence: n === 1 ? 1 : 0, exact: true });
  const word: WordSuggestion = { ...question(), location: loc(0), occurrence_locations: [loc(0), loc(1), loc(2)] };

  it("offers Show where in place of Show in document", () => {
    const html = renderToStaticMarkup(
      <WordCard suggestion={word} active={false} applied={false} note={null} actions={null} onSelect={() => {}} onSelectAt={() => {}} onApply={() => {}} />,
    );
    expect(html).toContain('data-testid="show-where"');
    expect(html).not.toContain('data-testid="select-in-document"');
  });

  it("keeps Show in document for an ordinary card", () => {
    const one: WordSuggestion = { ...word, occurrences: null, occurrence_locations: null };
    const html = renderToStaticMarkup(
      <WordCard suggestion={one} active={false} applied={false} note={null} actions={null} onSelect={() => {}} onSelectAt={() => {}} onApply={() => {}} />,
    );
    expect(html).toContain('data-testid="select-in-document"');
    expect(html).not.toContain("show-where");
  });
});

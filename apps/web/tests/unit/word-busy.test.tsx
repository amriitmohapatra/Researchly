import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { WordSuggestion } from "@researchly/contract";
import { WordBusyContext, WordCard } from "@/components/word/WordCard";
import { sugg } from "./helpers";

// Synthetic: one spelling card with a fix, signed in (mute and add-word offered).
const TEXT = "We fitted a modle to the counts.";
const S: WordSuggestion = {
  ...sugg("w-busy", 12, 17, "correction", { rule_id: "S001", tier: "spelling", text: TEXT.slice(12, 17), replacement: "model" }),
  location: { paragraph: 0, start: 12, end: 17, snippet: "modle", occurrence: 0, exact: true },
};

function card(busy: boolean): string {
  return renderToStaticMarkup(
    <WordBusyContext.Provider value={busy}>
      <WordCard
        suggestion={S}
        active={false}
        applied={false}
        note={null}
        actions={{ onMute: () => {}, onAddWord: () => {} }}
        onSelect={() => {}}
        onApply={() => {}}
      />
    </WordBusyContext.Provider>,
  );
}

// The busy state reaches the card's buttons through a context (2026-10-14
// performance pass), not a prop: every one of them must still say so.
describe("Word card buttons while Word is busy", () => {
  it("are all marked unavailable while busy", () => {
    const html = card(true);
    for (const id of ["select-in-document", "apply-fix", "mute-rule", "add-word"]) {
      const tag = html.match(new RegExp(`<button[^>]*data-testid="${id}"[^>]*>`))?.[0];
      expect(tag).toContain('aria-disabled="true"');
    }
  });

  it("are all available otherwise", () => {
    const html = card(false);
    expect(html).not.toContain("aria-disabled");
    for (const id of ["select-in-document", "apply-fix", "mute-rule", "add-word"]) expect(html).toContain(`data-testid="${id}"`);
  });
});

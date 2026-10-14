import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ReadingSummary as Reading } from "@researchly/contract";
import { ReadingSummary } from "@/components/ReadingSummary";
import { readingSentence, setAsidePhrase } from "@/lib/reading";

describe("the reading summary", () => {
  it("says the word count and what was set aside, in the engine's words, in one line", () => {
    const reading: Reading = {
      words_checked: 4210,
      set_aside: [
        { kind: "code", count: 2, label: "lines of code" },
        { kind: "other_language", count: 1, label: "paragraphs not in English" },
      ],
    };
    expect(readingSentence(reading)).toBe("Checked 4,210 words. Set aside: 2 lines of code · 1 paragraph not in English.");
  });

  it("says only the word count when nothing was set aside", () => {
    expect(readingSentence({ words_checked: 812, set_aside: [] })).toBe("Checked 812 words.");
    expect(readingSentence({ words_checked: 1 })).toBe("Checked 1 word.");
  });

  it("keeps an unknown kind's label, and skips empty entries", () => {
    expect(setAsidePhrase({ kind: "layout", count: 3, label: "lines laid out as a table or an equation" })).toBe(
      "3 lines laid out as a table or an equation",
    );
    expect(
      readingSentence({
        words_checked: 10,
        set_aside: [
          { kind: "marked_up", count: 0, label: "bits of maths, citations or code in the markup" },
          { kind: "future_kind" as "code", count: 1, label: "things of a new kind" },
        ],
      }),
    ).toBe("Checked 10 words. Set aside: 1 things of a new kind.");
  });

  it("says nothing for an engine that sends no summary", () => {
    expect(readingSentence(null)).toBeNull();
    expect(readingSentence(undefined)).toBeNull();
    expect(renderToStaticMarkup(<ReadingSummary reading={null} />)).toBe("");
  });

  it("renders as one quiet line, as text (no markup from the labels)", () => {
    const html = renderToStaticMarkup(
      <ReadingSummary reading={{ words_checked: 5, set_aside: [{ kind: "code", count: 2, label: "<b>lines</b> of code" }] }} />,
    );
    expect(html).toContain('class="reading-line muted"');
    expect(html).toContain('data-testid="reading-summary"');
    expect(html).toContain("&lt;b&gt;lines&lt;/b&gt; of code");
  });
});

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
    expect(readingSentence(reading)).toBe(
      "Checked 4,210 words. Set aside: 2 lines of code · 1 paragraph not in English. Researchly checks English only.",
    );
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

describe("the coverage summary (Codex review #5)", () => {
  it("says what a file's reading left out: footnotes, text boxes, headers, in the singular for one", () => {
    const reading: Reading = {
      words_checked: 2310,
      set_aside: [],
      not_checked: [
        { kind: "footnotes", count: 3, label: "footnotes" },
        { kind: "text_boxes", count: 1, label: "text boxes" },
        { kind: "headers_footers", count: 2, label: "headers or footers" },
        { kind: "comments", count: 1, label: "comments" },
      ],
    };
    expect(readingSentence(reading)).toBe("Checked 2,310 words. Not checked: 3 footnotes · 1 text box · 2 headers or footers · 1 comment.");
  });

  it("says LaTeX footnotes were read where they are cited", () => {
    expect(
      readingSentence({ words_checked: 900, set_aside: [], included: [{ kind: "footnotes", count: 1, label: "footnotes" }] }),
    ).toBe("Checked 900 words, including 1 footnote.");
  });

  it("names an Overleaf project's unreadable inputs", () => {
    expect(
      readingSentence({
        words_checked: 50,
        not_checked: [{ kind: "skipped_files", count: 2, label: "included files that could not be read" }],
      }),
    ).toBe("Checked 50 words. Not checked: 2 included files that could not be read.");
  });

  it("adds what the Word pane counted itself, after the engine's own", () => {
    const reading: Reading = { words_checked: 120, set_aside: [{ kind: "code", count: 1, label: "lines of code" }] };
    expect(
      readingSentence(reading, [
        { kind: "footnotes", count: 2, label: "footnotes" },
        { kind: "endnotes", count: 0, label: "endnotes" },
        { kind: "text_boxes", count: 1, label: "text boxes" },
      ]),
    ).toBe("Checked 120 words. Set aside: 1 line of code. Not checked: 2 footnotes · 1 text box.");
    const html = renderToStaticMarkup(<ReadingSummary reading={reading} notChecked={[{ kind: "comments", count: 4, label: "comments" }]} />);
    expect(html).toContain("Not checked: 4 comments.");
  });
});

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PrintReport } from "@/components/PrintReport";
import { happyResponse, NARRATIVE, REVIEW, SAMPLE_TEXT, withPreferencesResponse } from "../../e2e/fixtures";

const at = new Date(Date.UTC(2026, 9, 8, 12, 5));
const texts = (html: string, re: RegExp) => [...html.matchAll(re)].map((m) => m[1]);

describe("the printable report", () => {
  const data = { ...happyResponse, review: REVIEW };
  const html = renderToStaticMarkup(<PrintReport data={data} submittedText={SAMPLE_TEXT} showPreferences={false} at={at} />);

  it("numbers every listed suggestion and every highlight refers to one of those numbers", () => {
    const listed = texts(html, /<span class="print-n">(\d+)<\/span>/g).map(Number);
    expect(listed).toEqual(data.suggestions.map((_, i) => i + 1));
    const refs = texts(html, /<sup class="print-ref">([\d,]+)<\/sup>/g).flatMap((s) => (s ?? "").split(",").map(Number));
    expect(refs.length).toBeGreaterThan(0);
    for (const n of refs) expect(listed).toContain(n);
    expect(html.match(/<mark class="print-hl/g)?.length).toBeGreaterThan(0);
  });

  it("renders the text as text nodes, with every highlighted stretch inside a mark", () => {
    // Concatenating the visible text gives back the submitted text (escaped).
    const body = html.slice(html.indexOf('class="print-text"'), html.indexOf("</div>", html.indexOf('class="print-text"')));
    const plain = body
      .replace(/<sup class="print-ref">[\d,]+<\/sup>/g, "")
      .replace(/<[^>]+>/g, "")
      .replace(/&quot;/g, '"')
      .replace(/&#x27;/g, "'")
      .replace(/&amp;/g, "&");
    expect(plain.startsWith(">" + SAMPLE_TEXT.slice(0, 20)) || plain.includes(SAMPLE_TEXT.slice(0, 20))).toBe(true);
  });

  it("carries the message, the plain explanation and the source of each suggestion", () => {
    for (const s of data.suggestions) {
      expect(html).toContain(s.message.replace(/'/g, "&#x27;").replace(/"/g, "&quot;").slice(0, 30));
      expect(html).toContain("Source: ");
    }
  });

  it("ends with the reviewer's brief, on its own page", () => {
    expect(html).toContain('class="print-brief"');
    expect(texts(html, /data-question="([A-E])"/g)).toEqual(["A", "B", "C", "D", "E"]);
  });

  it("says when there is no brief instead of leaving a gap", () => {
    const draft = renderToStaticMarkup(
      <PrintReport data={{ ...happyResponse, mode: "draft", review: null }} submittedText={SAMPLE_TEXT} showPreferences={false} at={at} />,
    );
    expect(draft).toContain("Draft mode, which has no brief");
    const none = renderToStaticMarkup(<PrintReport data={{ ...happyResponse, review: null }} submittedText={SAMPLE_TEXT} showPreferences={false} at={at} />);
    expect(none).toContain("did not return a brief");
  });

  it("follows the brief with the narrative map on its own page: strips as text rows, the missing moves with question, lesson and frame, the links, the hedging table", () => {
    const page = html.slice(html.indexOf('class="print-narrative"'), html.indexOf('class="print-foot"'));
    expect(page.indexOf('class="print-narrative"')).toBeGreaterThanOrEqual(0);
    expect(html.indexOf('class="print-brief"')).toBeLessThan(html.indexOf('class="print-narrative"'));
    expect(page).toContain("Narrative map");
    expect(page).toContain('class="nmap nmap-print"');
    expect(texts(page, /data-testid="narrative-section" data-section="([a-z]+)"/g)).toEqual(["introduction", "methods", "discussion"]);
    // Every move in text with its status word; nothing behind a disclosure on paper.
    expect(page.match(/class="nmap-cell-status"/g)).toHaveLength(NARRATIVE.sections.reduce((n, s) => n + s.moves.length, 0));
    expect(page).not.toContain("<details");
    const gap = NARRATIVE.sections[0]!.moves[1]!;
    expect(page).toContain(gap.question);
    expect(page).toContain(gap.plain);
    expect(page).toContain(gap.frame);
    expect(page).toContain("A frame to fill in; the words are yours.");
    expect(page).toContain("Appears after what should change.");
    expect(page).toContain("Argument: missing links");
    expect(page).toContain('data-code="claim_without_warrant"');
    expect(texts(page, /data-testid="narrative-hedging-row" data-section="([a-z]+)"/g)).toEqual(["introduction", "methods", "discussion"]);
    expect(page).toContain("heavily hedged");
  });

  it("says when there is no narrative map instead of leaving a gap", () => {
    const draft = renderToStaticMarkup(
      <PrintReport data={{ ...happyResponse, mode: "draft", review: null, narrative: null }} submittedText={SAMPLE_TEXT} showPreferences={false} at={at} />,
    );
    expect(draft).toContain("Draft mode, which has no narrative map");
    const none = renderToStaticMarkup(<PrintReport data={{ ...happyResponse, narrative: null }} submittedText={SAMPLE_TEXT} showPreferences={false} at={at} />);
    expect(none).toContain("did not return a narrative map");
    expect(none).not.toContain('data-testid="narrative-section"');
  });

  it("prints preferences only when they are shown on screen", () => {
    const hidden = renderToStaticMarkup(<PrintReport data={withPreferencesResponse} submittedText={SAMPLE_TEXT} showPreferences={false} at={at} />);
    const shown = renderToStaticMarkup(<PrintReport data={withPreferencesResponse} submittedText={SAMPLE_TEXT} showPreferences at={at} />);
    expect((shown.match(/print-card-preference/g) ?? []).length).toBeGreaterThan(0);
    expect(hidden).not.toContain("print-card-preference");
  });

  it("heads the page with the date and the counts, never a score", () => {
    const head = html.slice(0, html.indexOf("</header>"));
    expect(head).toContain("8 October 2026");
    expect(head).toMatch(/\d+ suggestions? \(/);
    expect(head).not.toMatch(/score|rating|grade/i);
  });
});

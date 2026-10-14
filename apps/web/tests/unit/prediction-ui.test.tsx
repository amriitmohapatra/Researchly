import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PREDICTION_HELP, PredictionStrip, PredictionToggle, WORD_PREDICTION_HELP } from "@/components/PredictionStrip";
import { NextWords, nextWordsIdle } from "@/components/word/NextWords";
import type { PredictionSetting } from "@/lib/use-prediction";
import {
  canListen,
  canPredict,
  CURSOR_MOVED_MESSAGE,
  insertAtCursor,
  onSelectionChange,
  readCursorContext,
  type OfficeApi,
} from "@/lib/word/office";
import { installFakeOffice, type FakeWordConfig } from "../../e2e/fake-office";

const setting = (on: boolean): PredictionSetting => ({ on, set: () => undefined, note: null });

/* ---------- the website's strip ---------- */

describe("the prediction strip", () => {
  it("shows the candidates as buttons outside the tab order, and says them in a polite live region", () => {
    const html = renderToStaticMarkup(
      <PredictionStrip
        candidates={[
          { text: "interval", start: 0, end: 3, kind: "word" },
          { text: "confidence interval", start: 0, end: 3, kind: "term" },
        ]}
        onAccept={() => undefined}
      />,
    );
    expect(html).toContain('aria-live="polite"');
    expect(html).toContain("Suggested: interval. Tab to accept. Also: confidence interval.");
    expect(html.match(/data-testid="prediction-option"/g)).toHaveLength(2);
    expect(html.match(/tabindex="-1"/g)).toHaveLength(2);
    expect(html).toContain("to accept");
    expect(html).toContain("to dismiss");
  });

  it("is an empty live region when there is nothing to offer (so Tab moves focus as usual)", () => {
    const html = renderToStaticMarkup(<PredictionStrip candidates={null} onAccept={() => undefined} />);
    expect(html).toContain('aria-live="polite"');
    expect(html).not.toContain("prediction-option");
    expect(html).not.toContain("to accept");
  });
});

describe("the switch", () => {
  it("is a labelled switch, on or off as the setting says, with its help", () => {
    const on = renderToStaticMarkup(<PredictionToggle setting={setting(true)} />);
    expect(on).toContain('role="switch"');
    expect(on).toContain("Word prediction");
    expect(on).toContain('checked=""');
    expect(on).toContain(PREDICTION_HELP);
    const off = renderToStaticMarkup(<PredictionToggle setting={setting(false)} />);
    expect(off).not.toContain('checked=""');
  });

  it("says when the account could not keep the choice", () => {
    const html = renderToStaticMarkup(<PredictionToggle setting={{ ...setting(false), note: "Saved here only." }} />);
    expect(html).toContain('role="alert"');
    expect(html).toContain("Saved here only.");
  });

  it("never mentions Tab in Word, where words are clicked", () => {
    expect(WORD_PREDICTION_HELP).not.toMatch(/Tab/);
    const html = renderToStaticMarkup(<PredictionToggle setting={setting(true)} help={WORD_PREDICTION_HELP} showHelp />);
    expect(html).toContain('class="help"');
  });
});

/* ---------- the Word pane's "Next words" panel ---------- */

describe("the Next words panel", () => {
  it("is gone when the writer turned prediction off", () => {
    expect(renderToStaticMarkup(<NextWords engineUrl="http://engine.test" local={false} setting={setting(false)} />)).toBe("");
  });

  it("has a Hide control, and says why there is nothing when Word cannot share the cursor", () => {
    const html = renderToStaticMarkup(<NextWords engineUrl="http://engine.test" local={false} setting={setting(true)} />);
    expect(html).toContain("Next words");
    expect(html).toContain('data-testid="next-words-hide"');
    expect(html).toContain("share where the cursor is, so Next words is not available here");
  });

  it("idle lines say what happens and that nothing is added by itself", () => {
    expect(nextWordsIdle(null)).toMatch(/nothing is added otherwise/);
    expect(nextWordsIdle("selection")).toMatch(/not for selected text/);
    expect(nextWordsIdle("heading")).toMatch(/headings/);
  });
});

/** Synthetic sentences written for these tests. */
const PARAS = [
  { text: "Methods", styleBuiltIn: "Heading1" },
  { text: "We report the 95% confidence int", styleBuiltIn: "Normal" },
];

function fake(config: Partial<FakeWordConfig> = {}) {
  const target: Record<string, unknown> = {};
  const state = installFakeOffice(target, { paragraphs: PARAS, cursor: 1, cursorAt: PARAS[1]!.text.length, ...config });
  target.Word = target.__fakeWordNamespace;
  return { api: target as unknown as OfficeApi, state, target };
}

describe("reading the cursor in Word", () => {
  it("reads the paragraph up to the cursor (WordApi 1.3)", async () => {
    const { api } = fake({ cursorAt: 17 });
    expect(canPredict(api)).toBe(true);
    expect(await readCursorContext(api)).toEqual({ ok: true, before: "We report the 95%" });
  });

  it("offers nothing for selected words, in a heading, or in a Word older than 1.3", async () => {
    const sel = fake();
    sel.state.selection = { paragraph: 1, start: 0, end: 2, text: "We" };
    expect(await readCursorContext(sel.api)).toEqual({ ok: false, reason: "selection" });

    const heading = fake({ cursor: 0, cursorAt: 3 });
    expect(await readCursorContext(heading.api)).toEqual({ ok: false, reason: "heading" });

    const old = fake();
    old.api.Office.context.requirements.isSetSupported = () => false;
    expect(canPredict(old.api)).toBe(false);
    expect(await readCursorContext(old.api)).toEqual({ ok: false, reason: "unsupported" });
  });
});

describe("inserting a word in Word", () => {
  it("inserts only the rest of the word at the cursor, leaves Track Changes alone, and puts the cursor after it", async () => {
    const { api, state } = fake({ trackingMode: "TrackAll" });
    const r = await insertAtCursor(api, "erval", "We report the 95% confidence int");
    expect(r).toEqual({ ok: true });
    expect(state.paragraphs[1]!.text).toBe("We report the 95% confidence interval");
    expect(state.edits).toEqual([expect.objectContaining({ before: "", text: "erval", tracked: true })]);
    expect(state.trackingWrites).toEqual([]);
    expect(state.selection).toMatchObject({ paragraph: 1, start: 37, end: 37 });
  });

  it("inserts nothing when the text at the cursor is no longer what the words were offered for", async () => {
    const { api, state } = fake();
    const r = await insertAtCursor(api, "erval", "We report the 95% confidence in");
    expect(r).toEqual({ ok: false, message: CURSOR_MOVED_MESSAGE });
    expect(state.edits).toEqual([]);
    expect(state.paragraphs[1]!.text).toBe(PARAS[1]!.text);
  });

  it("inserts nothing for an empty insertion", async () => {
    const { api, state } = fake();
    expect((await insertAtCursor(api, "", PARAS[1]!.text)).ok).toBe(false);
    expect(state.edits).toEqual([]);
  });
});

describe("listening for the cursor", () => {
  it("subscribes to selection changes and unsubscribes", () => {
    const { api, state, target } = fake();
    expect(canListen(api)).toBe(true);
    let fired = 0;
    const stop = onSelectionChange(api, () => (fired += 1));
    expect(state.selectionHandlers).toBe(1);
    (target.__fakeWordSelectionChanged as () => void)();
    expect(fired).toBe(1);
    stop?.();
    expect(state.selectionHandlers).toBe(0);
  });

  it("returns null where Word has no such event (the panel offers a button instead)", () => {
    const { api } = fake();
    delete (api.Office as { EventType?: unknown }).EventType;
    expect(canListen(api)).toBe(false);
    expect(onSelectionChange(api, () => undefined)).toBeNull();
  });
});

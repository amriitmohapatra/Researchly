/**
 * The coverage summary in Word (Codex review #5): the check reads the body
 * only, so the pane counts what it leaves out (footnotes, endnotes,
 * comments, text boxes) where Word can count it without handing over text.
 * The fake Office (e2e/fake-office.ts) reports the counts as Word does.
 */
import { describe, expect, it } from "vitest";
import { countUnread, type OfficeApi } from "@/lib/word/office";
import { installFakeOffice, type FakeWordConfig } from "../../e2e/fake-office";

function fake(config: Partial<FakeWordConfig> = {}) {
  const target: Record<string, unknown> = {};
  installFakeOffice(target, { paragraphs: [{ text: "We fitted a renewal model." }], ...config });
  target.Word = target.__fakeWordNamespace;
  return target as unknown as OfficeApi;
}

const UNREAD = { footnotes: 3, endnotes: 0, comments: 2, shapes: ["TextBox", "Picture", "TextBox"] };

describe("countUnread", () => {
  it("counts footnotes, comments and text boxes (not pictures), and leaves out what is not there", async () => {
    const parts = await countUnread(fake({ api16: true, desktopApi: true, unread: UNREAD }));
    expect(parts).toEqual([
      { kind: "footnotes", count: 3, label: "footnotes" },
      { kind: "comments", count: 2, label: "comments" },
      { kind: "text_boxes", count: 2, label: "text boxes" },
    ]);
  });

  it("counts only what this Word supports: no notes before WordApi 1.5, no shapes without the desktop API", async () => {
    expect(await countUnread(fake({ unread: UNREAD }))).toEqual([{ kind: "comments", count: 2, label: "comments" }]);
    expect(await countUnread(fake({ api13: false, unread: UNREAD }))).toEqual([]);
  });

  it("never throws: a Word that cannot count gives no counts and the check goes ahead", async () => {
    expect(await countUnread(fake({ api16: true, desktopApi: true, unread: UNREAD, failures: { unread: true } }))).toEqual([]);
  });

  it("an ordinary document has nothing to report", async () => {
    expect(await countUnread(fake({ api16: true, desktopApi: true }))).toEqual([]);
  });
});

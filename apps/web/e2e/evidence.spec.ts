/**
 * Evidence-linked brief and map (Codex review #3) and the scope line (#4):
 * "Show in text" from the brief and the map outlines the sentence on the
 * website and selects it in Word; "Read as" checks again under another
 * scope. Synthetic text; the engine and Office are mocked.
 */
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { AnalyzeRequest, AnalyzeWordRequest, EvidenceLink, EvidenceSpan, ProfileInfo, ReviewReport } from "@researchly/contract";
import { ENGINE, NARRATIVE, REVIEW, SAMPLE_TEXT, responseFor } from "./fixtures";
import { check, json, mockEngine, paste } from "./helpers";
import { DOC, fakeOffice, fulfillJson, mockWordEngine, wordResponseFor, wordState, WORD_REVIEW } from "./word-fixtures";

/** A span of SAMPLE_TEXT in code points, as the engine sends it (the sample has astral characters before most sentences). */
function span(sentence: string): EvidenceSpan {
  const u16 = SAMPLE_TEXT.indexOf(sentence);
  if (u16 < 0) throw new Error(`fixture: "${sentence}" not in the sample`);
  const start = Array.from(SAMPLE_TEXT.slice(0, u16)).length;
  return { start, end: start + Array.from(sentence).length, text: sentence, line: 0, col: 0 };
}

const CLAIM = span("It is clearly proven that vector control reduces transmission.");
const GROUNDS = span("Dengue 🦟 remains a major burden across South-East Asia.");
const LINK: EvidenceLink = {
  kind: "causal_claim",
  label: "A causal claim",
  claim: CLAIM,
  evidence: GROUNDS,
  evidence_status: "detected",
  evidence_note: "The nearest sentence with a number, a citation or a reported finding, within two sentences.",
};
// One the text does not hold (an engine bug or a stale reply): no button, never a wrong place.
const OUTSIDE: EvidenceLink = {
  kind: "overclaim",
  label: "A strong verb",
  claim: { start: 5000, end: 5040, text: "A sentence beyond the end of the text.", line: 0, col: 0 },
  evidence: null,
  evidence_status: "not_detected",
  evidence_note: "No number, citation or reported finding was detected within two sentences of this claim.",
};

const SCOPED = (id: "whole" | "excerpt", guessed: boolean): NonNullable<ProfileInfo["scope"]> => ({
  id,
  label: id === "whole" ? "Whole document" : "Excerpt",
  guessed,
  note:
    id === "whole"
      ? "Read as a whole document (its headings: Introduction, Methods, Discussion): the sections a reader of this kind of document expects are asked for."
      : "Read as an excerpt, as you chose: sections that are not in it are not asked for.",
});

function reviewWithLinks(): ReviewReport {
  return {
    ...REVIEW,
    questions: REVIEW.questions.map((q) => (q.id === "C" ? { ...q, links: [LINK] } : q.id === "D" ? { ...q, links: [OUTSIDE] } : q)),
  };
}

function respond(req: AnalyzeRequest) {
  const base = responseFor(req);
  const scope = req.options?.document_scope === "excerpt" ? SCOPED("excerpt", false) : SCOPED("whole", true);
  return {
    ...base,
    suggestions: [],
    counts: { correction: 0, improvement: 0, convention: 0, preference: 0 },
    profile: { ...base.profile, scope, topical: [{ heading: "Methods in brief", section: "methods" }] },
    review: req.options?.review ? reviewWithLinks() : null,
    narrative: req.options?.narrative
      ? {
          ...NARRATIVE,
          sections: NARRATIVE.sections.map((s) => ({
            ...s,
            moves: s.moves.map((m) => (m.evidence === GROUNDS.text ? { ...m, span: GROUNDS } : m)),
          })),
        }
      : null,
  };
}

test("Show in text from the brief outlines the claim, and goes back to the button", async ({ page }) => {
  const calls = await mockEngine(page, (req, route) => json(route, 200, respond(req)));
  await page.goto("/");
  await paste(page, SAMPLE_TEXT);
  await check(page);
  // Auto is not sent: the engine infers the scope.
  expect(calls[0]!.options).not.toHaveProperty("document_scope");
  await expect(page.getByTestId("topical-line")).toHaveText(
    "Topical heading read from the wording under it: “Methods in brief” as Methods.",
  );

  await page.getByTestId("view-brief").click();
  const c = page.locator('[data-question="C"]');
  const link = c.getByTestId("evidence-link");
  await expect(link).toContainText("A causal claim");
  await expect(link.getByTestId("evidence-side")).toContainText("Its evidence (found nearby)");
  await expect(link.getByTestId("evidence-side")).toContainText(GROUNDS.text);
  // The point the text does not hold abstains: its sentence is quoted, with no button.
  const d = page.locator('[data-question="D"]').getByTestId("evidence-link");
  await expect(d).toContainText("A sentence beyond the end of the text.");
  await expect(d.getByTestId("show-evidence")).toHaveCount(0);

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);

  // The claim: the text comes back with exactly that sentence outlined (after an emoji), with focus on it.
  await link.getByTestId("show-evidence").first().click();
  await expect(page.getByTestId("view-suggestions")).toHaveAttribute("aria-selected", "true");
  const outlined = page.getByTestId("document").locator("[data-evidence]");
  await expect(outlined).toHaveText(CLAIM.text);
  await expect(outlined).toBeFocused();
  await expect(page.getByTestId("evidence-back")).toContainText("Outlined in the text: a sentence from the reviewer’s brief.");

  // Back: the brief, with focus on the button the writer came from.
  await page.getByTestId("evidence-back-button").click();
  await expect(page.getByTestId("view-brief")).toHaveAttribute("aria-selected", "true");
  await expect(c.getByTestId("show-evidence").first()).toBeFocused();

  // Its evidence: the other sentence, the emoji included.
  await c.getByTestId("evidence-side").getByTestId("show-evidence").click();
  await expect(page.getByTestId("document").locator("[data-evidence]")).toHaveText(GROUNDS.text);
  // Choosing the outlined sentence leads back too.
  await page.getByTestId("document").locator("[data-evidence]").click();
  await expect(page.getByTestId("view-brief")).toHaveAttribute("aria-selected", "true");
});

test("Show in text from the map, and Read as checks again with the scope", async ({ page }) => {
  const calls = await mockEngine(page, (req, route) => json(route, 200, respond(req)));
  await page.goto("/");
  await paste(page, SAMPLE_TEXT);
  await check(page);
  await page.getByTestId("view-narrative").click();
  const map = page.getByTestId("narrative-map");
  await expect(map.getByTestId("scope-note")).toContainText("Read as a whole document");
  const present = map.locator('[data-testid="narrative-present"][data-move="intro.territory"]');
  await present.getByText("Show the sentence").click();
  await present.getByTestId("show-evidence").click();
  await expect(page.getByTestId("document").locator("[data-evidence]")).toHaveText(GROUNDS.text);
  await expect(page.getByTestId("evidence-back")).toContainText("narrative map");
  await page.getByTestId("evidence-back-button").click();
  await expect(page.getByTestId("view-narrative")).toHaveAttribute("aria-selected", "true");

  // Read as: Excerpt checks again, sent explicitly, and the line says it was the writer's choice.
  await page.getByTestId("scope-select").selectOption("excerpt");
  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]!.options?.document_scope).toBe("excerpt");
  await expect(page.getByTestId("scope-note")).toContainText("as you chose");
  await expect(page.getByTestId("scope-select")).toHaveValue("excerpt");
});

test("Word: Show in text selects the claim and its evidence in the document", async ({ page }) => {
  const claimText = DOC[3]!.text;
  const evidenceText = "In order to estimate the effective reproduction number, a renewal model was fitted.";
  const loc = (paragraph: number, text: string, start: number) => ({
    paragraph,
    start,
    end: start + text.length,
    snippet: text,
    occurrence: 0,
    exact: true,
    begin16: start,
    end16: start + text.length,
  });
  const wordLink: EvidenceLink = {
    kind: "causal_claim",
    label: "A causal claim",
    claim: { start: 200, end: 200 + claimText.length, text: claimText, line: 0, col: 0, location: loc(3, claimText, 0) },
    evidence: { start: 10, end: 10 + evidenceText.length, text: evidenceText, line: 0, col: 0, location: loc(1, evidenceText, 0) },
    evidence_status: "detected",
    evidence_note: "The nearest sentence with a number, a citation or a reported finding, within two sentences.",
  };
  // A sentence the engine could not place in Word: quoted, with no button.
  const unplaced: EvidenceLink = { ...wordLink, kind: "aim", label: "The aim", claim: { ...wordLink.claim, location: null }, evidence: null, evidence_status: "not_applicable", evidence_note: "" };
  await fakeOffice(page);
  const calls = await mockWordEngine(page, ENGINE, {
    respond: (req: AnalyzeWordRequest, route) => {
      const base = wordResponseFor(req);
      return fulfillJson(route, 200, {
        ...base,
        profile: { ...base.profile, scope: SCOPED(req.options?.document_scope === "excerpt" ? "excerpt" : "whole", req.options?.document_scope !== "excerpt") },
        review: req.options?.review
          ? { ...WORD_REVIEW, questions: WORD_REVIEW.questions.map((q) => (q.id === "C" ? { ...q, links: [wordLink] } : q.id === "B" ? { ...q, links: [unplaced] } : q)) }
          : null,
      });
    },
  });
  await page.goto("/word");
  await page.getByTestId("check-document").click();
  await expect(page.getByTestId("tp-results")).toBeVisible();
  await page.getByTestId("view-brief").click();
  const c = page.locator('[data-question="C"]');
  await c.getByTestId("show-evidence").first().click();
  await expect.poll(async () => (await wordState(page)).selection).toEqual({ paragraph: 3, start: 0, end: claimText.length, text: claimText });
  await c.getByTestId("evidence-side").getByTestId("show-evidence").click();
  await expect.poll(async () => (await wordState(page)).selection?.text).toBe(evidenceText);
  await expect(page.locator('[data-question="B"]').getByTestId("show-evidence")).toHaveCount(0);

  // Read as, in the pane too: checks again with the scope.
  await page.getByTestId("scope-select").selectOption("excerpt");
  await expect.poll(() => calls.length).toBe(2);
  expect(calls[1]!.body.options?.document_scope).toBe("excerpt");
});

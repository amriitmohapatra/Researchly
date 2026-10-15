import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { EvidenceLink, EvidenceSpan, NarrativeMap as Map, ProfileInfo, ReviewReport } from "@researchly/contract";
import { EvidenceLinks, shortQuote } from "@/components/EvidenceLinks";
import { DocumentView } from "@/components/DocumentView";
import { NarrativeMap } from "@/components/NarrativeMap";
import { ReviewBrief } from "@/components/ReviewBrief";
import { ScopeLine } from "@/components/ScopeLine";
import { analysisOptions } from "@/lib/engine";
import {
  SCOPE_OPTIONS,
  evidenceHighlight,
  evidenceId,
  evidenceStatusWord,
  filePlace,
  isEvidenceId,
  placeable,
  scopeNote,
  showKey,
} from "@/lib/evidence";
import { topicalLine } from "@/lib/profiles";
import { resolveSpans, segment } from "@/lib/segments";

// Synthetic, with an emoji before the claim: code points and UTF-16 differ after it.
const TEXT = "Discussion\nAdmissions 📉 fell by 35% (Table 2). Spraying caused the fall in admissions.\n";
const cp = (s: string) => Array.from(TEXT).join("").indexOf(s); // UTF-16 index of s
const toCp = (u16: number) => Array.from(TEXT.slice(0, u16)).length;

function spanOf(sentence: string, extra: Partial<EvidenceSpan> = {}): EvidenceSpan {
  const start = toCp(cp(sentence));
  return { start, end: start + Array.from(sentence).length, text: sentence, line: 2, col: 1, ...extra };
}

const CLAIM = spanOf("Spraying caused the fall in admissions.");
const GROUNDS = spanOf("Admissions 📉 fell by 35% (Table 2).");

const PAIRED: EvidenceLink = {
  kind: "causal_claim",
  label: "A causal claim",
  claim: CLAIM,
  evidence: GROUNDS,
  evidence_status: "detected",
  evidence_note: "The nearest sentence with a number, a citation or a reported finding, within two sentences.",
};
const ALONE: EvidenceLink = {
  kind: "claim_without_grounds",
  label: "A claim with no evidence nearby",
  claim: CLAIM,
  evidence: null,
  evidence_status: "not_detected",
  evidence_note: "No number, citation or reported finding was detected within two sentences of this claim.",
};
const STATEMENT: EvidenceLink = { kind: "aim", label: "The aim", claim: CLAIM, evidence: null, evidence_status: "not_applicable", evidence_note: "" };

describe("evidence spans", () => {
  it("ids never clash with a suggestion's and say what they are", () => {
    expect(evidenceId(CLAIM)).toBe(`evidence~${CLAIM.start}-${CLAIM.end}`);
    expect(isEvidenceId(evidenceId(CLAIM))).toBe(true);
    expect(isEvidenceId("4fcbcef5e5a56b5c")).toBe(false);
  });

  it("places a span only inside the checked text", () => {
    const n = Array.from(TEXT).length;
    expect(placeable(CLAIM, n)).toBe(true);
    expect(placeable({ ...CLAIM, end: n + 1 }, n)).toBe(false);
    expect(placeable({ ...CLAIM, end: CLAIM.start }, n)).toBe(false);
    expect(placeable(null, n)).toBe(false);
  });

  it("outlines the exact sentence after an emoji (code points, not UTF-16)", () => {
    const resolved = resolveSpans(TEXT, [evidenceHighlight(CLAIM)]);
    expect(resolved).toHaveLength(1);
    const segs = segment(TEXT, resolved);
    const marked = segs.find((s) => s.kind === "text" && s.ids.length > 0);
    expect(marked && marked.kind === "text" ? marked.text : null).toBe("Spraying caused the fall in admissions.");
    const html = renderToStaticMarkup(<DocumentView segments={segs} activeId={null} onSelect={() => {}} />);
    expect(html).toContain('class="hl hl-evidence"');
    expect(html).toContain('data-evidence="true"');
    expect(html).not.toContain("hl-improvement");
  });

  it("names the file and line only for a project of several files", () => {
    expect(filePlace({ file: "sections/discussion.tex", file_line: 3 })).toBe("sections/discussion.tex, line 3");
    expect(filePlace({ file: null, file_line: null })).toBeNull();
  });

  it("words the evidence status without colour", () => {
    expect(evidenceStatusWord("detected")).toBe("found nearby");
    expect(evidenceStatusWord("not_detected")).toBe("not detected");
    expect(evidenceStatusWord("not_applicable")).toBeNull();
    expect(showKey("C-claim-0", CLAIM)).toBe(`C-claim-0:${CLAIM.start}-${CLAIM.end}`);
    expect(shortQuote("x ".repeat(80)).length).toBeLessThanOrEqual(60);
  });
});

describe("the claim beside its evidence", () => {
  it("shows both sentences and a Show in text button on each", () => {
    const html = renderToStaticMarkup(<EvidenceLinks links={[PAIRED]} where="C" onShow={() => {}} />);
    expect(html).toContain("A causal claim");
    expect(html).toContain("Its evidence");
    expect(html).toContain("(found nearby)");
    expect(html).toContain("Spraying caused the fall in admissions.");
    expect(html).toContain("Admissions 📉 fell by 35% (Table 2).");
    expect(html.match(/data-testid="show-evidence"/g)).toHaveLength(2);
    expect(html).toContain('aria-label="Show in text: Spraying caused the fall in admissions."');
  });

  it("says what was not detected and never invents a link", () => {
    const html = renderToStaticMarkup(<EvidenceLinks links={[ALONE]} where="D" onShow={() => {}} />);
    expect(html).toContain("(not detected)");
    expect(html).toContain("No number, citation or reported finding");
    expect(html.match(/data-testid="show-evidence"/g)).toHaveLength(1);
  });

  it("a statement that needs no evidence stands alone", () => {
    const html = renderToStaticMarkup(<EvidenceLinks links={[STATEMENT]} where="B" onShow={() => {}} />);
    expect(html).not.toContain("Its evidence");
  });

  it("has no button on paper, nor where the surface cannot show the span", () => {
    expect(renderToStaticMarkup(<EvidenceLinks links={[PAIRED]} where="C" />)).not.toContain("show-evidence");
    const html = renderToStaticMarkup(<EvidenceLinks links={[PAIRED]} where="C" onShow={() => {}} canShow={(s) => s.start === CLAIM.start} />);
    expect(html.match(/data-testid="show-evidence"/g)).toHaveLength(1);
  });

  it("names the file and line in a multi-file project", () => {
    const html = renderToStaticMarkup(
      <EvidenceLinks links={[{ ...PAIRED, claim: { ...CLAIM, file: "sections/discussion.tex", file_line: 3 } }]} where="C" onShow={() => {}} />,
    );
    expect(html).toContain("sections/discussion.tex, line 3");
  });
});

const REVIEW: ReviewReport = {
  source: "A named source",
  disclaimer: "",
  sections: ["discussion"],
  words: 20,
  top_rules: [],
  questions: [
    { id: "B", status: "not_detected", question: "What are the authors trying to achieve?", verdict: "No explicit aim was detected.", points: [], evidence: [], links: [] },
    {
      id: "C",
      status: "detected",
      question: "What are they claiming?",
      verdict: "1 causal claim detected.",
      points: [],
      evidence: ["Spraying caused the fall in admissions."],
      links: [PAIRED],
    },
    { id: "E", status: "detected", question: "What use can be made of this?", verdict: "The significance is stated.", points: [], evidence: ["An older engine’s quote."] },
  ],
};

describe("the brief with its evidence placed", () => {
  const html = renderToStaticMarkup(
    <ReviewBrief state={{ kind: "ready", review: REVIEW }} onShowInText={() => {}} scopeLine={<p data-testid="scope">scope</p>} />,
  );

  it("replaces the bare quotes with placed sentences where the engine sends them", () => {
    expect(html.match(/data-testid="evidence-links"/g)).toHaveLength(1);
    expect(html).toContain("Where question C rests in your text");
    // An older engine's quote (no links) still shows as before.
    expect(html).toContain("An older engine’s quote.");
    expect(html).not.toContain('<ul class="brief-evidence" aria-label="Evidence for question C');
  });

  it("carries the scope line under its introduction", () => {
    expect(html.indexOf("data-testid=\"scope\"")).toBeGreaterThan(html.indexOf("brief-intro"));
  });
});

const MAP: Map = {
  note: "Found 2 reviewer comments; 1 of them has a reply. A response to reviewers is described, not judged: each comment is shown beside its reply.",
  profile: "response-to-reviewers",
  source: "S",
  unmapped: [],
  missing_links: [
    {
      section: "discussion",
      label: "Discussion",
      code: "claim_without_warrant",
      message: "1 claim could not be linked to a reason nearby.",
      source: "S",
      evidence: ["Spraying caused the fall in admissions."],
      spans: [CLAIM],
    },
  ],
  hedging: [],
  sections: [
    {
      section: "discussion",
      label: "Discussion",
      sentences: 2,
      words: 12,
      present: 1,
      expected: 1,
      moves: [
        {
          id: "summary",
          label: "The main finding, restated",
          status: "present",
          question: "Q?",
          plain: "P",
          frame: "F",
          source: "S",
          evidence: "Admissions 📉 fell by 35% (Table 2).",
          note: "",
          span: GROUNDS,
        },
      ],
    },
  ],
  units: [
    { kind: "reviewer_comment", label: "Reviewer 1, comment 1", comment: CLAIM, reply: GROUNDS, learn_ref: "response-letter" },
    { kind: "reviewer_comment", label: "Reviewer 1, comment 2", comment: GROUNDS, reply: null, learn_ref: "response-letter" },
  ],
};

describe("the map with its evidence placed", () => {
  it("lists a response letter's comments beside their replies, judging none", () => {
    const html = renderToStaticMarkup(<NarrativeMap state={{ kind: "ready", narrative: MAP }} onShowInText={() => {}} />);
    expect(html.match(/data-testid="narrative-unit"/g)).toHaveLength(2);
    expect(html).toContain("Reviewer 1, comment 2");
    expect(html).toContain("No reply was recognised under this comment.");
    expect(html).not.toContain("not detected");
    // Comment, reply, comment; the present move; the link's sentence.
    expect(html.match(/data-testid="show-evidence"/g)).toHaveLength(5);
  });

  it("prints every sentence and no button", () => {
    const html = renderToStaticMarkup(<NarrativeMap state={{ kind: "ready", narrative: MAP }} variant="print" onShowInText={() => {}} />);
    expect(html).not.toContain("show-evidence");
    expect(html).toContain("Reviewer 1, comment 1");
  });
});

const SCOPE = {
  id: "excerpt" as const,
  label: "Excerpt",
  guessed: true,
  note: "Read as an excerpt (its only section is Methods): sections that are not in it are not asked for.",
};

describe("the scope line", () => {
  it("says what was assumed, with a Read as override", () => {
    const html = renderToStaticMarkup(<ScopeLine scope={SCOPE} value="auto" onChange={() => {}} />);
    expect(html).toContain(SCOPE.note);
    expect(html).toContain("Read as");
    expect(html).toContain("Auto (excerpt)");
    expect(SCOPE_OPTIONS.map((o) => o.value)).toEqual(["auto", "whole", "chapter", "excerpt"]);
  });

  it("is the line only on paper, and nothing from an engine without scopes", () => {
    expect(renderToStaticMarkup(<ScopeLine scope={SCOPE} />)).not.toContain("<select");
    expect(renderToStaticMarkup(<ScopeLine scope={null} onChange={() => {}} />)).toBe("");
    expect(scopeNote({ ...SCOPE, note: "  " })).toBeNull();
  });

  it("is sent only when the writer chose one", () => {
    expect(analysisOptions({ showPreferences: false, documentScope: "auto" })).not.toHaveProperty("document_scope");
    expect(analysisOptions({ showPreferences: false })).not.toHaveProperty("document_scope");
    expect(analysisOptions({ showPreferences: false, documentScope: "chapter" }).document_scope).toBe("chapter");
  });
});

describe("topical headings", () => {
  const base: ProfileInfo = { id: "general", label: "General", guessed: true, note: "", rules_off: [], evidence: "" };

  it("names the headings read from their wording", () => {
    expect(topicalLine({ ...base, topical: [{ heading: "Experiment 1: the baseline SEIR", section: "methods" }] })).toBe(
      "Topical heading read from the wording under it: “Experiment 1: the baseline SEIR” as Methods.",
    );
    expect(
      topicalLine({
        ...base,
        topical: [
          { heading: "Experiment 1", section: "methods" },
          { heading: "What the fits showed", section: "results" },
        ],
      }),
    ).toBe("Topical headings read from the wording under them: “Experiment 1” as Methods and “What the fits showed” as Results.");
  });

  it("says nothing when there are none", () => {
    expect(topicalLine(base)).toBeNull();
    expect(topicalLine(null)).toBeNull();
  });
});

/**
 * The Word add-in's e2e document and engine answers (S3). The document is
 * synthetic (written for these tests); responses are typed with
 * `satisfies` so a contract change breaks the tests' build, not their meaning.
 */
import type { Page, Route } from "@playwright/test";
import type { AnalyzeWordRequest, AnalyzeWordResponse, HealthResponse, TierHealth, WordSuggestion } from "@researchly/contract";
import { fakeOfficeScript, type FakeWordConfig, type FakeWordState } from "./fake-office";

export const OFFICE_JS = "https://appsforoffice.microsoft.com/lib/1/hosted/office.js";
export const LOCAL_ENGINE = "http://localhost:3517";

export const DOC: FakeWordConfig["paragraphs"] = [
  { text: "Methods", styleBuiltIn: "Heading1" },
  {
    text: "In order to estimate the effective reproduction number, a renewal model was fitted. The the priors were weakly informative for nowcasting.",
    styleBuiltIn: "Normal",
  },
  { text: "Discussion", styleBuiltIn: "Heading1" },
  { text: "It is clearly proven that the the effect of vector control was large, and the the data agree.", styleBuiltIn: "Normal" },
  { text: "Region", tableNestingLevel: 1 },
];

const OFFSETS = (() => {
  const out: number[] = [];
  let pos = 0;
  for (const p of DOC) {
    out.push(pos);
    pos += p.text.length + 2;
  }
  return out;
})();

/** Where match number `occurrence` of `needle` sits in paragraph `paragraph`. */
export function at(paragraph: number, needle: string, occurrence = 0): number {
  const text = DOC[paragraph]!.text;
  let i = -1;
  for (let n = 0; n <= occurrence; n++) {
    i = text.indexOf(needle, n === 0 ? 0 : i + needle.length);
    if (i < 0) throw new Error(`fixture: "${needle}" #${occurrence} not in paragraph ${paragraph}`);
  }
  return i;
}

function wsugg(
  id: string,
  paragraph: number,
  needle: string,
  occurrence: number,
  extra: Partial<WordSuggestion> & Pick<WordSuggestion, "rule_id" | "rule_name" | "message">,
  exact = true,
  spanLength = needle.length,
): WordSuggestion {
  const start = at(paragraph, needle, occurrence);
  const end = start + spanLength;
  const text = DOC[paragraph]!.text.slice(start, end);
  return {
    id,
    category: "improvement",
    tier: "craft",
    section: paragraph < 2 ? "methods" : "discussion",
    why: "A synthetic explanation for the e2e suite.",
    plain: "In everyday words: the same advice, written for a reader who knows their science but not the grammar terms.",
    source: "The Craft of Scientific Writing, §4",
    fix_safety: "review",
    confidence: 1,
    replacement: null,
    span: { start: OFFSETS[paragraph]! + start, end: OFFSETS[paragraph]! + end, line: 1, col: start + 1 },
    text,
    location: { paragraph, start, end, snippet: needle, occurrence, exact },
    ...extra,
  };
}

export const WORDY = wsugg("w-wordy", 1, "In order to", 0, {
  rule_id: "C120",
  rule_name: "Wordy phrase",
  message: "‘In order to’ can usually be ‘To’.",
  replacement: "To",
  fix_safety: "safe",
});
export const REPEAT_1 = wsugg("w-repeat-1", 1, "The the", 0, {
  rule_id: "S010",
  rule_name: "Repeated word",
  category: "correction",
  tier: "spelling",
  message: "‘the’ is repeated.",
  replacement: "The",
});
export const NOWCASTING = wsugg("w-spell", 1, "nowcasting", 0, {
  rule_id: "S001",
  rule_name: "Possible misspelling",
  category: "correction",
  tier: "spelling",
  message: "‘nowcasting’ is not in the dictionary.",
});
export const LONG = wsugg(
  "w-long",
  3,
  "It is clearly proven",
  0,
  {
    rule_id: "G106",
    rule_name: "Long sentence",
    message: "This sentence is long; consider splitting it.",
  },
  false,
  DOC[3]!.text.length,
);
export const BOOSTER = wsugg("w-booster", 3, "clearly proven", 0, {
  rule_id: "C201",
  rule_name: "Booster overclaims certainty",
  category: "convention",
  message: "‘clearly proven’ claims more certainty than the evidence can carry.",
});
export const REPEAT_2A = wsugg("w-repeat-2a", 3, "the the", 0, {
  rule_id: "S010",
  rule_name: "Repeated word",
  category: "correction",
  tier: "spelling",
  message: "‘the’ is repeated.",
  replacement: "the",
});
export const REPEAT_2B = wsugg("w-repeat-2b", 3, "the the", 1, {
  rule_id: "S010",
  rule_name: "Repeated word",
  category: "correction",
  tier: "spelling",
  message: "‘the’ is repeated (second time in this sentence).",
  replacement: "the",
});

export const HEALTHY: TierHealth[] = [
  { tier: "parser", label: "Parser", ok: true, state: "ready", detail: "spaCy en_core_web_sm", remedy: "" },
  { tier: "spelling", label: "Spelling", ok: true, state: "ready", detail: "SymSpell", remedy: "" },
  { tier: "grammar", label: "Grammar", ok: true, state: "ready", detail: "LanguageTool", remedy: "" },
  { tier: "gec", label: "Learned corrections", ok: false, state: "missing", detail: "no local model", remedy: "" },
];

export const DEGRADED: TierHealth[] = HEALTHY.map((t) =>
  t.tier === "grammar"
    ? { ...t, ok: false, state: "error", detail: "LanguageTool did not respond in time", remedy: "Check again in a minute" }
    : t,
);

const ALL = [WORDY, REPEAT_1, NOWCASTING, LONG, BOOSTER, REPEAT_2A, REPEAT_2B];

export const reviseResponse = {
  schema_version: "1",
  signed_in: false,
  warnings: [],
  mode: "revise",
  hidden_by_mode: 0,
  suggestions: ALL,
  counts: { correction: 4, improvement: 2, convention: 1 },
  hidden_preferences: 1,
  metrics: null,
  sections_detected: ["methods", "discussion"],
  health: HEALTHY,
  engine: { service_version: "0.3.0", core_version: "0.9.0", rules_loaded: 90 },
  elapsed_ms: 321,
  coverage: {
    paragraphs: DOC.length,
    table_paragraphs: 1,
    not_checked: ["footnotes", "endnotes", "headers and footers", "text boxes", "comments"],
  },
} satisfies AnalyzeWordResponse;

/** Draft: document-level checks held back (the long-sentence and booster cards stay; these are sentence-level). */
export const draftResponse = {
  ...reviseResponse,
  mode: "draft",
  hidden_by_mode: 2,
} satisfies AnalyzeWordResponse;

export const healthResponse = (tiers: TierHealth[] = HEALTHY) =>
  ({
    status: tiers.some((t) => !t.ok && t.tier !== "gec") ? "degraded" : "ok",
    tiers,
    engine: reviseResponse.engine,
  }) satisfies HealthResponse;

/* ---------- page setup ---------- */

/** Serve the fake office.js in place of Microsoft's, configured for this test. */
export async function fakeOffice(page: Page, config: Partial<FakeWordConfig> = {}) {
  const full: FakeWordConfig = { paragraphs: DOC, ...config };
  await page.addInitScript((cfg) => {
    (window as unknown as { __fakeWordConfig: unknown }).__fakeWordConfig = cfg;
  }, full);
  await page.route(OFFICE_JS, (route) =>
    route.fulfill({ status: 200, contentType: "application/javascript", body: fakeOfficeScript() }),
  );
}

export function wordState(page: Page): Promise<FakeWordState> {
  return page.evaluate(() => (window as unknown as { __fakeWord: FakeWordState }).__fakeWord);
}

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "POST, GET, OPTIONS",
  "access-control-allow-headers": "content-type, authorization",
  "access-control-expose-headers": "retry-after, x-request-id",
};

export interface WordCall {
  url: string;
  body: AnalyzeWordRequest;
  authorization: string | undefined;
}

/** Mock one engine's /v1/analyze-word and /v1/health. */
export async function mockWordEngine(
  page: Page,
  base: string,
  opts: {
    respond?: (req: AnalyzeWordRequest, route: Route) => Promise<void> | void;
    health?: TierHealth[];
  } = {},
): Promise<WordCall[]> {
  const calls: WordCall[] = [];
  await page.route(`${base}/v1/**`, async (route) => {
    const req = route.request();
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    const path = new URL(req.url()).pathname;
    if (path === "/v1/health") {
      return route.fulfill({ status: 200, headers: CORS, contentType: "application/json", body: JSON.stringify(healthResponse(opts.health)) });
    }
    if (path !== "/v1/analyze-word") return route.fulfill({ status: 404, headers: CORS, body: "" });
    const body = req.postDataJSON() as AnalyzeWordRequest;
    calls.push({ url: req.url(), body, authorization: req.headers()["authorization"] });
    if (opts.respond) return opts.respond(body, route);
    const data = body.options?.mode === "draft" ? draftResponse : reviseResponse;
    return route.fulfill({ status: 200, headers: CORS, contentType: "application/json", body: JSON.stringify(data) });
  });
  return calls;
}

export function fulfillJson(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, headers: CORS, contentType: "application/json", body: JSON.stringify(body) });
}
